# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import io
from io import BytesIO
import traceback

# --- CONFIGURATION & CONSTANTES ---
st.set_page_config(page_title="Rapports Cleemy", layout="wide")

PERIOD_TRANSLATION = {"Day": "par Jour", "None": "par Dépense", "Month": "par Mois", "Year": "par An"}

# --- FONCTIONS DE TRAITEMENT DES DONNÉES ---

def safe_get(data, key, default):
    """Fonction utilitaire pour obtenir une valeur ou un défaut sûr (liste/dict)."""
    val = data.get(key, default)
    if val is None:
        return default
    return val

@st.cache_data
def load_and_process_data(uploaded_file: io.BytesIO) -> dict | None:
    """
    Charge, valide et pré-traite les données JSON de manière très robuste.
    """
    try:
        uploaded_file.seek(0)
        data = json.load(uploaded_file)

        if not isinstance(data, dict) or "profiles" not in data or "natures" not in data:
            st.error("❌ Fichier invalide : la structure de base (clés `profiles`, `natures`) est incorrecte.")
            return {"error": "Structure de base invalide", "raw_data": data}

        nature_lookup = {
            n.get('id'): n.get('multilingualName', {}).get('fr-FR', f"ID {n.get('id')}")
            for n in safe_get(data, 'natures', []) if isinstance(n, dict) and n.get('id') is not None
        }

        df_profiles = _create_profile_nature_df(data, nature_lookup)
        df_limits = _create_limits_df(data, nature_lookup)
        nature_to_profiles_map = _create_nature_to_profiles_map(data)

        return {
            "raw_data": data,
            "nature_lookup": nature_lookup,
            "df_profiles": df_profiles,
            "df_limits": df_limits,
            "nature_to_profiles_map": nature_to_profiles_map,
            "error": None
        }
    except json.JSONDecodeError:
        st.error("❌ Le fichier fourni n'est pas un JSON valide.")
        return {"error": "JSONDecodeError"}
    except Exception as e:
        st.error(f"Une erreur critique est survenue lors du traitement : {e}")
        tb_str = traceback.format_exc()
        try:
            uploaded_file.seek(0)
            raw_display_data = uploaded_file.read().decode('utf-8')
        except:
            raw_display_data = "Impossible de lire le contenu du fichier pour le débogage."
        return {"error": tb_str, "raw_data": raw_display_data}

def _create_profile_nature_df(data: dict, nature_lookup: dict) -> pd.DataFrame:
    export_data = []
    for profile in safe_get(data, 'profiles', []):
        if not isinstance(profile, dict): continue
        profil_name = safe_get(profile, 'multilingualName', {}).get('fr-FR', f"ID {profile.get('id', 'N/A')}")
        for id_nature in safe_get(profile, 'idNatures', []):
            export_data.append({
                "Profil": profil_name,
                "ID Nature": id_nature,
                "Nom de la nature": nature_lookup.get(id_nature, "❓ Inconnu"),
            })
    return pd.DataFrame(export_data)

def _create_limits_df(data: dict, nature_lookup: dict) -> pd.DataFrame:
    limits_data = []
    for profile in safe_get(data, 'profiles', []):
        if not isinstance(profile, dict): continue
        profile_name = safe_get(profile, 'multilingualName', {}).get('fr-FR', f"ID {profile.get('id', 'N/A')}")

        for limit in safe_get(profile, 'limits', []):
            if not isinstance(limit, dict): continue
            nature_names = [nature_lookup.get(nid, f"ID {nid}") for nid in safe_get(limit, 'idNatures', [])]
            thresholds = safe_get(limit, 'thresholds', [{}])[0]
            limits_data.append({
                "Profil": profile_name, "Type de Règle": "Limite",
                "Natures Concernées": ", ".join(filter(None, nature_names)),
                "Type de Plafond": limit.get('type', 'N/A').capitalize(),
                "Montant": thresholds.get('amount', 'N/A'),
                "Devise": limit.get('currencyCode', ''),
                "Période": PERIOD_TRANSLATION.get(limit.get('period', 'N/A'), limit.get('period', 'N/A'))
            })

        for allowance in safe_get(profile, 'allowances', []):
            if not isinstance(allowance, dict): continue
            nature_names = [nature_lookup.get(nid, f"ID {nid}") for nid in safe_get(allowance, 'idNatures', [])]
            thresholds = safe_get(allowance, 'thresholds', [{}])[0]
            limits_data.append({
                "Profil": profile_name, "Type de Règle": "Indemnité",
                "Natures Concernées": ", ".join(filter(None, nature_names)),
                "Type de Plafond": "Forfait",
                "Montant": thresholds.get('amount', 'N/A'),
                "Devise": allowance.get('currencyCode', ''), "Période": "N/A"
            })
    return pd.DataFrame(limits_data)

def _create_nature_to_profiles_map(data: dict) -> dict:
    nature_map = {}
    profiles_list = safe_get(data, 'profiles', [])
    if not isinstance(profiles_list, list):
        profiles_list = []

    for profile in profiles_list:
        if not isinstance(profile, dict): continue
        profile_name = safe_get(profile, 'multilingualName', {}).get('fr-FR', f"ID {profile.get('id', 'N/A')}")

        for nature_id in safe_get(profile, 'idNatures', []):
            nature_map.setdefault(nature_id, {}).setdefault(profile_name, {"limits": [], "allowances": []})

        for limit in safe_get(profile, 'limits', []):
            if not isinstance(limit, dict): continue
            for nature_id in safe_get(limit, 'idNatures', []):
                profile_rules = nature_map.setdefault(nature_id, {}).setdefault(profile_name, {"limits": [], "allowances": []})
                profile_rules["limits"].append(limit)

        for allowance in safe_get(profile, 'allowances', []):
            if not isinstance(allowance, dict): continue
            for nature_id in safe_get(allowance, 'idNatures', []):
                profile_rules = nature_map.setdefault(nature_id, {}).setdefault(profile_name, {"limits": [], "allowances": []})
                profile_rules["allowances"].append(allowance)
    return nature_map

# --- GÉNÉRATION DU RAPPORT PDF ---
def create_pdf_report(df: pd.DataFrame) -> bytes:
    """
    Génère un rapport PDF avec la syntaxe moderne de fpdf2, sans avertissements.
    """
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", 'B', size=12)
    pdf.cell(
        0, 10, "Rapport d'analyse Cleemy",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        align='C'
    )
    pdf.ln(10)

    num_columns = len(df.columns) if len(df.columns) > 0 else 1
    col_width = 190 / num_columns

    pdf.set_font("Helvetica", 'B', size=8)
    for header in df.columns:
        safe_header = str(header).encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(col_width, 10, safe_header, border=1, align='C')
    pdf.ln()

    pdf.set_font("Helvetica", '', size=8)
    for _, row in df.iterrows():
        for col in df.columns:
            safe_text = str(row[col]).encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(col_width, 10, safe_text, border=1)
        pdf.ln()
            
    return bytes(pdf.output())

# --- INTERFACES DES ONGLETS ---
def build_overview_ui(df_profiles: pd.DataFrame):
    """Affiche l'onglet Vue d'ensemble avec exports CSV, PDF, et Excel."""
    st.header("📖 Vue d'ensemble des associations Profils/Natures")
    st.write("Utilisez ce tableau pour une vue globale, filtrer ou exporter les données.")

    profils_uniques = sorted(df_profiles["Profil"].unique().tolist())
    options = ["Tous"] + profils_uniques

    if "overview_select" not in st.session_state:
        st.session_state.overview_select = "Tous"

    selected_profil = st.selectbox(
        "🔍 Filtrer par profil",
        options=options,
        key="overview_select"
    )

    col_reset, _ = st.columns([1, 5])
    if col_reset.button("🔄 Réinitialiser le filtre"):
        st.session_state.overview_select = "Tous"
        st.rerun() # Utilise st.rerun() qui est la syntaxe moderne

    display_df = df_profiles if selected_profil == "Tous" else df_profiles[df_profiles["Profil"] == selected_profil]

    if display_df.empty:
        st.warning("Aucun résultat pour ce filtre.")
    else:
        st.dataframe(display_df, use_container_width=True)
        st.divider()
        st.subheader("🚀 Exports")
        col1, col2, col3 = st.columns(3)
        
        with col1: # Export CSV
            csv_data = display_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Télécharger en CSV", data=csv_data,
                file_name='rapport_profils.csv', mime='text/csv', use_container_width=True
            )
        
        with col2: # Export PDF
            pdf_bytes = create_pdf_report(display_df)
            st.download_button(
                label="📄 Télécharger en PDF", data=pdf_bytes,
                file_name="rapport_profils.pdf", mime="application/pdf", use_container_width=True
            )
        
        with col3: # Export Excel (XLSX)
            xlsx_output = BytesIO()
            with pd.ExcelWriter(xlsx_output, engine='openpyxl') as writer:
                display_df.to_excel(writer, index=False, sheet_name='Rapport')
            st.download_button(
                label="📊 Télécharger en Excel", data=xlsx_output.getvalue(),
                file_name="rapport_profils.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

def build_profile_analysis_ui(data: dict, nature_lookup: dict):
    st.header("👤 Analyse détaillée par Profil")
    st.write("Choisissez un profil pour afficher en détail sa configuration complète.")

    profiles = {p.get('multilingualName', {}).get('fr-FR', f"ID {p.get('id', 'N/A')}"): p for p in safe_get(data, 'profiles', []) if isinstance(p, dict)}
    sorted_profiles = sorted(profiles.keys())
    selected_profil_name = st.selectbox("Sélectionnez un profil", options=sorted_profiles, key="profile_select")

    if not selected_profil_name: return

    profile = profiles[selected_profil_name]
    st.divider()
    st.subheader(f"Détails pour : {selected_profil_name}")

    st.markdown("##### Natures associées")
    id_natures = safe_get(profile, 'idNatures', [])
    nature_names = [nature_lookup.get(nid, f"ID {nid}") for nid in id_natures]
    st.dataframe({"Natures": sorted(nature_names)}, use_container_width=True)

    st.markdown("##### Limites de Dépenses (Plafonds)")
    limits = safe_get(profile, 'limits', [])
    if not limits:
        st.info("Aucune limite spécifique n'est définie.")
    else:
        limit_messages = []
        for limit in limits:
            thresholds = safe_get(limit, 'thresholds', [{}])[0]
            amount, currency = thresholds.get('amount', 'N/A'), limit.get('currencyCode', '')
            limit_type, period = limit.get('type', 'N/A').capitalize(), limit.get('period', 'N/A')
            nature_names_limit = [nature_lookup.get(nid, f"ID {nid}") for nid in safe_get(limit, 'idNatures', [])]
            prefix = "🛑" if limit_type == "Absolute" else "⚠️"
            message = f"{prefix} **{limit_type}** → **{amount} {currency}** {PERIOD_TRANSLATION.get(period, period)} pour : **{', '.join(filter(None, nature_names_limit))}**"
            limit_messages.append(message)
        st.markdown("\n\n".join(limit_messages))

    st.markdown("##### Indemnités Forfaitaires (Allowances)")
    allowances = safe_get(profile, 'allowances', [])
    if not allowances:
        st.info("Aucune indemnité forfaitaire n'est définie.")
    else:
        allowance_messages = []
        for allowance in allowances:
            thresholds = safe_get(allowance, 'thresholds', [{}])[0]
            amount, currency = thresholds.get('amount', 'N/A'), allowance.get('currencyCode', '')
            nature_names_allowance = [nature_lookup.get(nid, f"ID {nid}") for nid in safe_get(allowance, 'idNatures', [])]
            message = f"✅ **Forfait** → **{amount} {currency}** pour : **{', '.join(filter(None, nature_names_allowance))}**"
            allowance_messages.append(message)
        st.markdown("\n\n".join(allowance_messages))

def build_limits_analysis_ui(df_limits: pd.DataFrame):
    st.header("📏 Analyse comparative des Limites et Indemnités")
    st.write("Ce tableau centralise toutes les règles de tous les profils pour faciliter leur comparaison.")
    if df_limits.empty:
        st.warning("Aucune limite ou indemnité n'a été trouvée dans le fichier.")
    else:
        st.dataframe(df_limits, use_container_width=True)

def build_accounting_plan_ui(data: dict):
    st.header("🧾 Analyse du Plan Comptable par Nature")
    st.write("Choisissez une nature pour voir son imputation comptable dans chaque plan.")

    costs_accounts_lookup = {}
    for chart in safe_get(data, 'chartsOfAccounts', []):
        if not isinstance(chart, dict): continue
        chart_id = chart.get('id')
        if chart_id is None: continue

        accounts_dict = {}
        for acc in safe_get(chart, 'costsAccounts', []):
            if not isinstance(acc, dict): continue
            acc_id = acc.get('id')
            if acc_id is None: continue
            
            format_list = safe_get(acc, 'format', [])
            value = format_list[0].get('value', 'N/A') if format_list else 'N/A'
            accounts_dict[acc_id] = value
            
        costs_accounts_lookup[chart_id] = accounts_dict

    natures_list = sorted([(n.get('multilingualName', {}).get('fr-FR', f"ID {n['id']}"), n['id']) for n in safe_get(data, 'natures', []) if isinstance(n, dict)])
    
    selected_nature_name = st.selectbox("Choisissez une nature à analyser", options=[n[0] for n in natures_list], key="accounting_select")
    st.divider()

    if selected_nature_name:
        selected_nature_id = next((n[1] for n in natures_list if n[0] == selected_nature_name), None)
        found = False
        if selected_nature_id is not None:
            for chart in safe_get(data, 'chartsOfAccounts', []):
                if not isinstance(chart, dict): continue
                for mapping in safe_get(chart, 'natureAccountMappings', []):
                    if not isinstance(mapping, dict): continue
                    if mapping.get('idNature') == selected_nature_id:
                        found = True
                        with st.expander(f"**{chart.get('name')}**", expanded=True):
                            id_costs_account = mapping.get('idCostsAccount')
                            compte_de_charge = costs_accounts_lookup.get(chart.get('id'), {}).get(id_costs_account, 'Non trouvé')
                            tva_ids = safe_get(mapping, 'vatOptions', {}).get('idCountryVats', [])
                            st.markdown(f"**Compte de charge :** `{compte_de_charge}`")
                            st.markdown(f"**ID de TVA applicables :** `{', '.join(map(str, tva_ids)) or 'Aucun'}`")
        if not found:
            st.warning(f"La nature **{selected_nature_name}** n'est associée à aucun plan comptable.")

def build_nature_analysis_ui(nature_lookup: dict, nature_to_profiles_map: dict):
    st.header("🔬 Analyse détaillée par Nature")
    st.write("Choisissez une nature pour voir tous les profils et les règles qui s'y appliquent.")

    natures_list = sorted(nature_lookup.items(), key=lambda item: item[1])
    selected_nature_id = st.selectbox(
        "Sélectionnez une nature",
        options=[n[0] for n in natures_list],
        format_func=lambda x: nature_lookup.get(x, "N/A"),
        key="nature_select"
    )
    st.divider()

    if not selected_nature_id: return

    profiles_for_nature = nature_to_profiles_map.get(selected_nature_id, {})
    if not profiles_for_nature:
        st.warning("Aucun profil n'utilise cette nature.")
        return

    st.subheader(f"Profils et règles pour : {nature_lookup[selected_nature_id]}")
    for profile_name, rules in sorted(profiles_for_nature.items()):
        with st.container():
            st.markdown(f"#### Profil : {profile_name}")

            if not rules["limits"] and not rules["allowances"]:
                st.info("Ce profil utilise cette nature sans limite ni indemnité spécifique.")

            if rules["limits"]:
                st.markdown("###### Limites (Plafonds)")
                for limit in rules["limits"]:
                    thresholds = safe_get(limit, 'thresholds', [{}])[0]
                    amount, currency = thresholds.get('amount', 'N/A'), limit.get('currencyCode', '')
                    limit_type, period = limit.get('type', 'N/A').capitalize(), limit.get('period', 'N/A')
                    message = f"**{limit_type}** → **{amount} {currency}** {PERIOD_TRANSLATION.get(period, period)}"
                    if limit_type == "Absolute":
                        st.error(f"🛑 {message}")
                    else:
                        st.warning(f"⚠️ {message}")

            if rules["allowances"]:
                st.markdown("###### Indemnités (Allowances)")
                for allowance in rules["allowances"]:
                    thresholds = safe_get(allowance, 'thresholds', [{}])[0]
                    amount, currency = thresholds.get('amount', 'N/A'), allowance.get('currencyCode', '')
                    st.success(f"✅ **Forfait** → **{amount} {currency}**")
            st.divider()

# --- POINT D'ENTRÉE PRINCIPAL ---
def main():
    st.title("📊 Rapports d'analyse Cleemy")
    uploaded_file = st.file_uploader("Déposez votre fichier `Full.json` ici", type="json")

    if uploaded_file:
        processed_data = load_and_process_data(uploaded_file)

        with st.expander("🔍 Inspecter les données et les erreurs"):
            if processed_data and "raw_data" in processed_data:
                if processed_data.get("error"):
                    st.json(processed_data["raw_data"], expanded=False)
            if processed_data and processed_data.get("error"):
                st.subheader("Trace de l'erreur :")
                st.code(processed_data["error"], language='text')

        if processed_data and processed_data.get("error") is None:
            st.toast("Fichier traité avec succès !", icon="✅")
            
            tabs_titles = [
                "📖 Vue d'Ensemble", "👤 Analyse par Profil", "🔬 Analyse par Nature",
                "📏 Analyse des Limites", "🧾 Analyse Plan Comptable"
            ]
            tab1, tab2, tab3, tab4, tab5 = st.tabs(tabs_titles)

            with tab1:
                build_overview_ui(processed_data["df_profiles"])
            with tab2:
                build_profile_analysis_ui(processed_data["raw_data"], processed_data["nature_lookup"])
            with tab3:
                build_nature_analysis_ui(processed_data["nature_lookup"], processed_data["nature_to_profiles_map"])
            with tab4:
                build_limits_analysis_ui(processed_data["df_limits"])
            with tab5:
                build_accounting_plan_ui(processed_data["raw_data"])
    else:
        st.info("👋 En attente d'un fichier JSON pour commencer l'analyse.")

if __name__ == "__main__":
    main()