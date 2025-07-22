# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
from fpdf import FPDF # pip install fpdf2
from collections import defaultdict

# --- Configuration de la page Streamlit ---
st.set_page_config(page_title="Rapports Cleemy", layout="wide")

# --- Fonctions utilitaires ---
def safe_latin1(val) -> str:
    """Encode une valeur pour éviter les erreurs d'encodage dans FPDF."""
    return str(val).encode('latin-1', 'replace').decode('latin-1')

# --- Fonctions de traitement des données ---

@st.cache_data(hash_funcs={"_io.BytesIO": lambda _: None})
def load_data(uploaded_file) -> dict:
    """Charge le contenu du fichier JSON uploadé et le met en cache."""
    return json.load(uploaded_file)

@st.cache_data
def process_profile_data(data: dict) -> pd.DataFrame:
    """Crée un DataFrame plat pour la vue d'ensemble Profils/Natures."""
    nature_lookup = {
        n['id']: n.get('multilingualName', {}).get('fr-FR', f"ID {n['id']}")
        for n in data.get('natures', [])
    }
    
    export_data = []
    for profile in data.get("profiles", []):
        profil_name = profile.get('multilingualName', {}).get('fr-FR', f"ID {profile.get('id', 'N/A')}")
        for id_nature in profile.get("idNatures", []):
            export_data.append({
                "Profil": profil_name,
                "ID Nature": id_nature,
                "Nom de la nature": nature_lookup.get(id_nature, "❓ Inconnu"),
            })
    return pd.DataFrame(export_data)

@st.cache_data
def process_limits_data(data: dict) -> pd.DataFrame:
    """Crée un DataFrame de toutes les limites et indemnités pour une analyse centralisée."""
    nature_lookup = {
        n['id']: n.get('multilingualName', {}).get('fr-FR', f"ID {n['id']}")
        for n in data.get('natures', [])
    }
    period_translation = {"Day": "par Jour", "None": "par Dépense", "Month": "par Mois", "Year": "par An"}
    
    limits_data = []
    for profile in data.get("profiles", []):
        profile_name = profile.get('multilingualName', {}).get('fr-FR', f"ID {profile.get('id', 'N/A')}")
        
        for limit in profile.get('limits', []):
            nature_names = [nature_lookup.get(nid) for nid in limit.get('idNatures', [])]
            limits_data.append({
                "Profil": profile_name,
                "Type de Règle": "Limite",
                "Natures Concernées": ", ".join(filter(None, nature_names)),
                "Type de Plafond": limit.get('type', 'N/A').capitalize(),
                "Montant": limit.get('thresholds', [{}])[0].get('amount', 'N/A'),
                "Devise": limit.get('currencyCode', ''),
                "Période": period_translation.get(limit.get('period', 'N/A'), limit.get('period', 'N/A'))
            })
            
        for allowance in profile.get('allowances', []):
            nature_names = [nature_lookup.get(nid) for nid in allowance.get('idNatures', [])]
            limits_data.append({
                "Profil": profile_name,
                "Type de Règle": "Indemnité",
                "Natures Concernées": ", ".join(filter(None, nature_names)),
                "Type de Plafond": "Forfait",
                "Montant": allowance.get('thresholds', [{}])[0].get('amount', 'N/A'),
                "Devise": allowance.get('currencyCode', ''),
                "Période": "N/A"
            })
            
    return pd.DataFrame(limits_data)

# --- Génération du rapport PDF ---
def create_pdf_report(df: pd.DataFrame) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "Rapport d'analyse Cleemy", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', size=8)

    max_lengths = {col: df[col].astype(str).str.len().max() for col in df.columns}
    header_lengths = {col: len(col) for col in df.columns}
    final_lengths = {col: max(max_lengths.get(col, 0), header_lengths.get(col, 0)) for col in df.columns}
    total_len = sum(final_lengths.values()) if sum(final_lengths.values()) > 0 else 1
    col_widths = [(final_lengths[col] / total_len) * 190 for col in df.columns]

    for i, header in enumerate(df.columns):
        pdf.cell(float(col_widths[i]), 10, safe_latin1(header), border=1, align='C')
    pdf.ln()
    pdf.set_font("Arial", size=8)

    for _, row in df.iterrows():
        for i, col in enumerate(df.columns):
            pdf.cell(float(col_widths[i]), 10, safe_latin1(row[col]), border=1)
        pdf.ln()
        
    return bytes(pdf.output())

# --- INTERFACES DES ONGLETS ---

def build_overview_ui(df_profiles: pd.DataFrame):
    st.header("📖 Vue d'ensemble des associations Profils/Natures")
    st.write("Utilisez ce tableau pour une vue globale, filtrer ou exporter les données.")
    
    profils_uniques = sorted(df_profiles["Profil"].unique().tolist())
    selected_profil = st.selectbox("🔍 Filtrer par profil", options=["Tous"] + profils_uniques)

    display_df = df_profiles if selected_profil == "Tous" else df_profiles[df_profiles["Profil"] == selected_profil]

    if display_df.empty:
        st.warning("Aucun résultat pour ce filtre.")
    else:
        st.dataframe(display_df, use_container_width=True)

    st.divider()
    st.subheader("🚀 Exports")
    col1, col2 = st.columns(2)
    with col1:
        csv_data = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger la vue en CSV",
            data=csv_data,
            file_name=f'rapport_profils_natures_{selected_profil.replace(" ", "_")}.csv',
            mime='text/csv',
            use_container_width=True
        )
    with col2:
        pdf_bytes = create_pdf_report(display_df)
        st.download_button(
            label="📄 Télécharger la vue en PDF",
            data=pdf_bytes,
            file_name=f"rapport_profils_natures_{selected_profil.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

def build_profile_analysis_ui(data: dict):
    st.header("👤 Analyse détaillée par Profil")
    st.write("Choisissez un profil pour afficher en détail sa configuration complète.")

    nature_lookup = {n['id']: n.get('multilingualName', {}).get('fr-FR', f"ID {n['id']}") for n in data.get('natures', [])}
    profiles = {p.get('multilingualName', {}).get('fr-FR', f"ID {p.get('id', 'N/A')}"): p for p in data.get('profiles', [])}
    
    selected_profil_name = st.selectbox("Sélectionnez un profil", options=sorted(profiles.keys()))

    if selected_profil_name:
        profile = profiles[selected_profil_name]
        st.divider()
        st.subheader(f"Détails pour : {selected_profil_name}")

        st.markdown("##### Natures associées")
        id_natures = profile.get('idNatures', [])
        nature_names = [nature_lookup.get(nid, f"ID {nid}") for nid in id_natures]
        st.dataframe({"Natures": sorted(nature_names)}, use_container_width=True)

        period_translation = {"Day": "par Jour", "None": "par Dépense", "Month": "par Mois", "Year": "par An"}
        
        # --- DÉBUT DE LA CORRECTION ---
        # On construit une liste de messages texte au lieu de plusieurs widgets st.error/warning
        st.markdown("##### Limites de Dépenses (Plafonds)")
        limits = profile.get('limits', [])
        if not limits:
            st.info("Aucune limite spécifique n'est définie.")
        else:
            limit_messages = []
            for limit in limits:
                amount, currency = limit.get('thresholds', [{}])[0].get('amount', 'N/A'), limit.get('currencyCode', '')
                limit_type, period = limit.get('type', 'N/A').capitalize(), limit.get('period', 'N/A')
                nature_names_limit = [nature_lookup.get(nid) for nid in limit.get('idNatures', [])]
                
                prefix = "🛑" if limit_type == "Absolute" else "⚠️"
                message = f"{prefix} **{limit_type}** → **{amount} {currency}** {period_translation.get(period, period)} pour : **{', '.join(filter(None, nature_names_limit))}**"
                limit_messages.append(message)
            st.markdown("\n\n".join(limit_messages))

        st.markdown("##### Indemnités Forfaitaires (Allowances)")
        allowances = profile.get('allowances', [])
        if not allowances:
            st.info("Aucune indemnité forfaitaire n'est définie.")
        else:
            allowance_messages = []
            for allowance in allowances:
                amount, currency = allowance.get('thresholds', [{}])[0].get('amount', 'N/A'), allowance.get('currencyCode', '')
                nature_names_allowance = [nature_lookup.get(nid) for nid in allowance.get('idNatures', [])]
                message = f"✅ **Forfait** → **{amount} {currency}** pour : **{', '.join(filter(None, nature_names_allowance))}**"
                allowance_messages.append(message)
            st.markdown("\n\n".join(allowance_messages))
        # --- FIN DE LA CORRECTION ---

def build_limits_analysis_ui(data: dict):
    st.header("📏 Analyse comparative des Limites et Indemnités")
    st.write("Ce tableau centralise toutes les règles de tous les profils pour faciliter leur comparaison.")
    
    df_limits = process_limits_data(data)
    if df_limits.empty:
        st.warning("Aucune limite ou indemnité n'a été trouvée dans le fichier.")
        return
        
    st.dataframe(df_limits, use_container_width=True)
    
def build_accounting_plan_ui(data: dict):
    st.header("🧾 Analyse du Plan Comptable par Nature")
    st.write("Choisissez une nature pour voir son imputation comptable dans chaque plan.")

    natures_list = sorted([(n.get('multilingualName', {}).get('fr-FR', f"ID {n['id']}"), n['id']) for n in data.get('natures', [])])
    costs_accounts_lookup = {
        chart['id']: {
            acc['id']: (acc.get('format')[0].get('value', 'N/A') if acc.get('format') else 'N/A')
            for acc in chart.get('costsAccounts', [])
        } for chart in data.get('chartsOfAccounts', [])
    }
    
    selected_nature_name = st.selectbox("Choisissez une nature à analyser", options=[n[0] for n in natures_list])
    st.divider()

    if selected_nature_name:
        selected_nature_id = next(n[1] for n in natures_list if n[0] == selected_nature_name)
        found = False
        for chart in data.get('chartsOfAccounts', []):
            for mapping in chart.get('natureAccountMappings', []):
                if mapping.get('idNature') == selected_nature_id:
                    found = True
                    with st.expander(f"**{chart.get('name')}**", expanded=True):
                        id_costs_account = mapping.get('idCostsAccount')
                        compte_de_charge = costs_accounts_lookup.get(chart['id'], {}).get(id_costs_account, 'Non trouvé')
                        tva_ids = mapping.get('vatOptions', {}).get('idCountryVats', [])
                        
                        st.markdown(f"**Compte de charge :** `{compte_de_charge}`")
                        st.markdown(f"**ID de TVA applicables :** `{', '.join(map(str, tva_ids)) or 'Aucun'}`")
        if not found:
            st.warning(f"La nature **{selected_nature_name}** n'est associée à aucun plan comptable.")

def build_nature_analysis_ui(data: dict):
    st.header("🔬 Analyse détaillée par Nature")
    st.write("Choisissez une nature pour voir tous les profils et les règles qui s'y appliquent.")

    nature_lookup = {n['id']: n.get('multilingualName', {}).get('fr-FR', f"ID {n['id']}") for n in data.get('natures', [])}
    natures_list = sorted(nature_lookup.items(), key=lambda item: item[1])

    selected_nature_id = st.selectbox("Sélectionnez une nature", options=[n[0] for n in natures_list], format_func=lambda x: nature_lookup.get(x, "N/A"))
    st.divider()

    if selected_nature_id:
        st.subheader(f"Profils et règles pour : {nature_lookup[selected_nature_id]}")
        profiles_with_nature = defaultdict(lambda: {"limits": [], "allowances": []})

        for profile in data.get("profiles", []):
            if selected_nature_id in profile.get("idNatures", []):
                profile_name = profile.get('multilingualName', {}).get('fr-FR', f"ID {profile.get('id', 'N/A')}")
                for limit in profile.get('limits', []):
                    if selected_nature_id in limit.get('idNatures', []):
                        profiles_with_nature[profile_name]["limits"].append(limit)
                for allowance in profile.get('allowances', []):
                    if selected_nature_id in allowance.get('idNatures', []):
                        profiles_with_nature[profile_name]["allowances"].append(allowance)
        
        if not profiles_with_nature:
            st.warning("Aucun profil n'utilise cette nature ou n'a de règle spécifique pour elle.")
            return

        period_translation = {"Day": "par Jour", "None": "par Dépense", "Month": "par Mois", "Year": "par An"}
        
        for profile_name, rules in sorted(profiles_with_nature.items()):
            st.subheader(f"Profil : {profile_name}")
            
            if not rules["limits"] and not rules["allowances"]:
                st.info("Ce profil utilise cette nature sans limite ni indemnité spécifique.")
            
            if rules["limits"]:
                st.markdown("###### Limites (Plafonds)")
                for limit in rules["limits"]:
                    amount, currency = limit.get('thresholds', [{}])[0].get('amount', 'N/A'), limit.get('currencyCode', '')
                    limit_type, period = limit.get('type', 'N/A').capitalize(), limit.get('period', 'N/A')
                    message = f"**{limit_type}** → **{amount} {currency}** {period_translation.get(period, period)}"
                    st.error(message) if limit_type == "Absolute" else st.warning(message)

            if rules["allowances"]:
                st.markdown("###### Indemnités (Allowances)")
                for allowance in rules["allowances"]:
                    amount, currency = allowance.get('thresholds', [{}])[0].get('amount', 'N/A'), allowance.get('currencyCode', '')
                    st.success(f"**Forfait** → **{amount} {currency}**")
            
            st.divider()

# --- Point d'entrée principal ---
def main() -> None:
    st.title("📊 Rapports d'analyse Cleemy")
    uploaded_file = st.file_uploader("Déposez votre fichier `Full.json` ici", type="json")

    if uploaded_file:
        try:
            with st.spinner("⏳ Traitement en cours..."):
                raw_data = load_data(uploaded_file)
            st.toast("Fichier chargé avec succès !", icon="✅")
            
            if "profiles" not in raw_data or "natures" not in raw_data:
                st.error("❌ Fichier invalide : clés `profiles` ou `natures` manquantes.")
                return

            tabs = [
                "📖 Vue d'Ensemble",
                "👤 Analyse par Profil",
                "📏 Analyse des Limites",
                "🧾 Analyse Plan Comptable",
                "🔬 Analyse par Nature"
            ]
            tab1, tab2, tab3, tab4, tab5 = st.tabs(tabs)

            with tab1:
                df_profiles = process_profile_data(raw_data)
                build_overview_ui(df_profiles)
            with tab2:
                build_profile_analysis_ui(raw_data)
            with tab3:
                build_limits_analysis_ui(raw_data)
            with tab4:
                build_accounting_plan_ui(raw_data)
            with tab5:
                build_nature_analysis_ui(raw_data)
                
        except Exception as e:
            st.error(f"Une erreur inattendue est survenue : {e}")
            st.exception(e)
    else:
        st.info("👋 En attente d'un fichier JSON pour commencer l'analyse.")

if __name__ == "__main__":
    main()