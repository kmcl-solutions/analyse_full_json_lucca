# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import json
from fpdf import FPDF # Assurez-vous d'avoir installé fpdf2 (pip install fpdf2)

# --- Configuration de la page Streamlit ---
st.set_page_config(page_title="Rapports Cleemy", layout="wide")

# --- Fonctions de traitement des données ---

@st.cache_data
def load_data(uploaded_file) -> dict:
    """Charge le contenu du fichier JSON uploadé et le met en cache."""
    return json.load(uploaded_file)

@st.cache_data
def process_profile_data(data: dict) -> pd.DataFrame:
    """
    Traite les données JSON pour créer un DataFrame pour le rapport Profils/Natures.
    Le résultat est mis en cache pour éviter les retraitements.
    """
    nature_dict = {}
    for nature in data.get("natures", []):
        is_valid = nature.get("isValid", True)
        is_enabled = nature.get("isEnabled", True)
        
        if not is_valid:
            statut = "❌ Invalide"
        elif not is_enabled:
            statut = "⛔ Désactivée"
        else:
            statut = "✅ Valide"
            
        nature_dict[nature.get("id")] = {
            "name": nature.get("multilingualName", {}).get("fr-FR", "❓ (non traduit)"),
            "status": statut
        }

    export_data = []
    for profile in data.get("profiles", []):
        profil_name = profile.get('multilingualName', {}).get('fr-FR', f"ID {profile.get('id', 'N/A')}")
        for id_nature in profile.get("idNatures", []):
            nature_info = nature_dict.get(id_nature, {"name": "❓ Inconnu", "status": "❓"})
            
            export_data.append({
                "Profil": profil_name,
                "ID Nature": id_nature,
                "Nom de la nature": nature_info["name"],
                "Statut": nature_info["status"],
                "ID Compte de coût": "N/A" 
            })
            
    return pd.DataFrame(export_data)

# --- Fonctions de génération de rapport ---

def create_pdf_report(df: pd.DataFrame) -> bytes:
    """Génère un rapport PDF tabulaire propre à partir du DataFrame."""
    
    df_for_pdf = df.copy()
    df_for_pdf['Statut'] = df_for_pdf['Statut'].str.replace('✅ ', '', regex=False)
    df_for_pdf['Statut'] = df_for_pdf['Statut'].str.replace('❌ ', '', regex=False)
    df_for_pdf['Statut'] = df_for_pdf['Statut'].str.replace('⛔ ', '', regex=False)
    df_for_pdf = df_for_pdf[['Profil', 'ID Nature', 'Nom de la nature', 'Statut']]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    pdf.cell(0, 10, "Rapport Complet - Profils & Natures", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', size=8)
    
    col_widths = [60, 20, 80, 30] 
    headers = df_for_pdf.columns
    
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, str(header), border=1, align='C')
    pdf.ln()
    
    pdf.set_font("Arial", size=8)
    
    for _, row in df_for_pdf.iterrows():
        pdf.cell(col_widths[0], 10, str(row['Profil']).encode('latin-1', 'replace').decode('latin-1'), border=1)
        pdf.cell(col_widths[1], 10, str(row['ID Nature']), border=1)
        pdf.cell(col_widths[2], 10, str(row['Nom de la nature']).encode('latin-1', 'replace').decode('latin-1'), border=1)
        pdf.cell(col_widths[3], 10, str(row['Statut']).encode('latin-1', 'replace').decode('latin-1'), border=1)
        pdf.ln()

    return pdf.output()

# --- Interfaces Utilisateur ---

def build_profiles_ui(data: dict, df_profiles: pd.DataFrame):
    """Construit l'interface pour le rapport Profils & Natures, incluant les limites."""
    st.header("🗂️ Vue groupée par Profil")
    st.write("Cliquez sur un profil pour voir le détail des natures, limites et indemnités associées.")
    st.write("")

    nature_lookup = {
        n['id']: n.get('multilingualName', {}).get('fr-FR', f"ID {n['id']}")
        for n in data.get('natures', [])
    }
    
    period_translation = {"Day": "par Jour", "None": "par Dépense"}

    for profile in data.get('profiles', []):
        profile_name = profile.get('multilingualName', {}).get('fr-FR', f"ID {profile.get('id', 'N/A')}")
        id_natures_in_profile = profile.get('idNatures', [])
        
        with st.expander(f"**Profil : {profile_name}** ({len(id_natures_in_profile)} natures)"):
            st.markdown("##### Natures associées")
            details_df = df_profiles[df_profiles['Profil'] == profile_name].drop(columns=['Profil', 'ID Compte de coût'])
            st.dataframe(details_df, use_container_width=True)
            
            st.markdown("---")
            st.markdown("##### Limites de Dépenses (Plafonds)")
            limits = profile.get('limits', [])
            if not limits:
                st.info("Aucune limite spécifique n'est définie pour ce profil.")
            else:
                for limit in limits:
                    amount = limit.get('thresholds', [{}])[0].get('amount', 'N/A')
                    currency = limit.get('currencyCode', '')
                    limit_type = limit.get('type', 'N/A').capitalize()
                    period = limit.get('period', 'N/A')
                    nature_ids = limit.get('idNatures', [])
                    nature_names = [nature_lookup.get(nid, f"ID {nid}") for nid in nature_ids]
                    message = f"**{limit_type}** → **{amount} {currency}** {period_translation.get(period, period)} pour : **{', '.join(nature_names)}**"
                    if limit_type == "Absolute":
                        st.error(message)
                    else:
                        st.warning(message)
                        
            st.markdown("##### Indemnités Forfaitaires (Allowances)")
            allowances = profile.get('allowances', [])
            if not allowances:
                st.info("Aucune indemnité forfaitaire n'est définie pour ce profil.")
            else:
                for allowance in allowances:
                    amount = allowance.get('thresholds', [{}])[0].get('amount', 'N/A')
                    currency = allowance.get('currencyCode', '')
                    nature_ids = allowance.get('idNatures', [])
                    nature_names = [nature_lookup.get(nid, f"ID {nid}") for nid in nature_ids]
                    st.success(f"**Forfait** → **{amount} {currency}** pour : **{', '.join(nature_names)}**")

    st.divider()
    with st.expander("🔎 Outils d'analyse et Exports"):
        st.subheader("🚀 Exports")
        csv_data = df_profiles.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger le rapport Profils/Natures en CSV",
            data=csv_data,
            file_name='rapport_profils_natures.csv',
            mime='text/csv',
            use_container_width=True
        )

def build_accounting_plan_ui(data: dict):
    """Construit l'interface pour l'analyse des plans comptables par nature."""
    st.header("🧾 Analyse du Plan Comptable par Nature")
    
    natures_list = [
        (n.get('multilingualName', {}).get('fr-FR', f"ID {n['id']}"), n['id'])
        for n in data.get('natures', [])
    ]
    natures_list.sort(key=lambda x: x[0])

    # --- DÉBUT DE LA CORRECTION ---
    # Création du dictionnaire de recherche pour les comptes de charge
    costs_accounts_lookup = {}
    for chart in data.get('chartsOfAccounts', []):
        # Pour chaque plan, on crée un sous-dictionnaire pour ses comptes
        costs_accounts_lookup[chart['id']] = {
            acc['id']: (
                # On prend la valeur du premier élément de la liste 'format'...
                acc.get('format')[0].get('value', 'N/A')
                # ... SEULEMENT SI la liste 'format' existe et n'est pas vide.
                if acc.get('format') 
                # Sinon, la valeur par défaut est 'N/A'.
                else 'N/A'
            )
            for acc in chart.get('costsAccounts', [])
        }
    # --- FIN DE LA CORRECTION ---

    selected_nature_name = st.selectbox(
        "Choisissez une nature à analyser :",
        options=[n[0] for n in natures_list]
    )
    
    st.divider()

    if selected_nature_name:
        selected_nature_id = next(n[1] for n in natures_list if n[0] == selected_nature_name)
        st.subheader(f"Détails comptables pour : {selected_nature_name}")
        
        found_in_any_plan = False
        for chart in data.get('chartsOfAccounts', []):
            for mapping in chart.get('natureAccountMappings', []):
                if mapping.get('idNature') == selected_nature_id:
                    found_in_any_plan = True
                    with st.expander(f"**{chart.get('name')}**", expanded=True):
                        id_costs_account = mapping.get('idCostsAccount')
                        compte_de_charge = costs_accounts_lookup.get(chart['id'], {}).get(id_costs_account, 'Non trouvé')
                        vat_options = mapping.get('vatOptions', {})
                        tva_ids = vat_options.get('idCountryVats', [])
                        
                        st.markdown(f"**Compte de charge :** `{compte_de_charge}`")
                        st.markdown("**Catégorie de coût :** `Aucun` (donnée non disponible)")
                        st.markdown("**Compte de charge secondaire :** `Aucun` (donnée non disponible)")
                        st.markdown(f"**ID de TVA applicables :** `{', '.join(map(str, tva_ids)) or 'Aucun'}`")

        if not found_in_any_plan:
            st.warning(f"La nature **{selected_nature_name}** n'est associée à aucun plan comptable.")

# --- Point d'entrée principal de l'application ---

def main():
    """Fonction principale qui orchestre l'application Streamlit."""
    st.title("📊 Rapports d'analyse Cleemy")

    uploaded_file = st.file_uploader(
        "Déposez votre fichier `Full.json` exporté depuis Cleemy ici", 
        type="json"
    )

    if uploaded_file:
        try:
            raw_data = load_data(uploaded_file)
            
            tab1, tab2 = st.tabs(["Rapport Profils & Natures", "Analyse Plan Comptable"])

            with tab1:
                df_profiles = process_profile_data(raw_data)
                build_profiles_ui(raw_data, df_profiles)

            with tab2:
                build_accounting_plan_ui(raw_data)

        except Exception as e:
            st.error(f"Une erreur est survenue lors du traitement du fichier : {e}")
            st.exception(e) 
            st.warning("Le fichier est peut-être corrompu ou son format est inattendu.")
    else:
        st.info("👋 En attente d'un fichier JSON pour commencer l'analyse.")

if __name__ == "__main__":
    main()
