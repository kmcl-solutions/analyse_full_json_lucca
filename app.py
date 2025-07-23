# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import io
from io import BytesIO
import traceback
from pydantic import BaseModel, Field, ValidationError, conlist
from typing import List, Optional
from enum import Enum

# --- CONFIGURATION & CONSTANTES ---
st.set_page_config(page_title="Rapports NDF", layout="wide")

PERIOD_TRANSLATION = {"Day": "par Jour", "None": "par Dépense", "Month": "par Mois", "Year": "par An"}

class JsonKeys(str, Enum):
    PROFILES = "profiles"
    NATURES = "natures"
    LIMITS = "limits"
    ALLOWANCES = "allowances"
    ID = "id"
    ID_NATURES = "idNatures"
    MULTILINGUAL_NAME = "multilingualName"
    CURRENCY_CODE = "currencyCode"
    THRESHOLDS = "thresholds"
    AMOUNT = "amount"
    TYPE = "type"
    PERIOD = "period"
    CHARTS_OF_ACCOUNTS = "chartsOfAccounts"
    COSTS_ACCOUNTS = "costsAccounts"
    FORMAT = "format"
    VALUE = "value"
    NAME = "name"
    NATURE_ACCOUNT_MAPPINGS = "natureAccountMappings"
    ID_NATURE = "idNature"
    ID_COSTS_ACCOUNT = "idCostsAccount"
    VAT_OPTIONS = "vatOptions"
    ID_COUNTRY_VATS = "idCountryVats"
    FR_FR = "fr-FR"


# --- MODÈLES PYDANTIC ---
class Threshold(BaseModel):
    amount: Optional[float] = None

class Limit(BaseModel):
    idNatures: List[int] = Field(default_factory=list)
    type: Optional[str] = None
    period: Optional[str] = None
    currencyCode: Optional[str] = None
    thresholds: conlist(Threshold, max_length=1) = Field(default_factory=list)

class Allowance(BaseModel):
    idNatures: List[int] = Field(default_factory=list)
    currencyCode: Optional[str] = None
    thresholds: conlist(Threshold, max_length=1) = Field(default_factory=list)

class Profile(BaseModel):
    id: Optional[int] = None
    multilingualName: dict = Field(default_factory=dict)
    idNatures: List[int] = Field(default_factory=list)
    limits: List[Limit] = Field(default_factory=list)
    allowances: List[Allowance] = Field(default_factory=list)
    
    @property
    def name_fr(self) -> str:
        name = self.multilingualName.get(JsonKeys.FR_FR)
        if name:
            return name
        if self.id is not None:
            return f"Profil sans nom (ID: {self.id})"
        return "Profil non identifié"

class Nature(BaseModel):
    id: int
    multilingualName: dict = Field(default_factory=dict)
    
    @property
    def name_fr(self) -> str:
        return self.multilingualName.get(JsonKeys.FR_FR, f"ID {self.id}")

class CostsAccount(BaseModel):
    id: int
    format: conlist(dict, max_length=1) = Field(default_factory=list)
    
    @property
    def value(self) -> str:
        return self.format[0].get(JsonKeys.VALUE, 'N/A') if self.format else 'N/A'

class NatureAccountMapping(BaseModel):
    idNature: int
    idCostsAccount: Optional[int] = None
    vatOptions: dict = Field(default_factory=dict)
    
    @property
    def vat_ids(self) -> List[str]:
        return self.vatOptions.get(JsonKeys.ID_COUNTRY_VATS, [])

class ChartOfAccounts(BaseModel):
    id: int
    name: Optional[str] = None
    costsAccounts: List[CostsAccount] = Field(default_factory=list)
    natureAccountMappings: List[NatureAccountMapping] = Field(default_factory=list)

class CleemyData(BaseModel):
    profiles: List[Profile] = Field(default_factory=list)
    natures: List[Nature] = Field(default_factory=list)
    chartsOfAccounts: List[ChartOfAccounts] = Field(default_factory=list)


# --- FONCTIONS DE TRAITEMENT ET D'AUDIT DES DONNÉES ---
@st.cache_data(hash_funcs={BytesIO: lambda _: None})
def load_and_process_data(uploaded_file: io.BytesIO) -> dict | None:
    """Charge, valide avec Pydantic et pré-traite les données JSON."""
    with st.spinner("Analyse et validation du fichier en cours..."):
        try:
            uploaded_file.seek(0)
            raw_data = json.load(uploaded_file)
            data = CleemyData.model_validate(raw_data)

            nature_lookup = {n.id: n.name_fr for n in data.natures}
            df_profiles = _create_profile_nature_df(data, nature_lookup)
            df_limits = _create_limits_df(data, nature_lookup)
            nature_to_profiles_map = _create_nature_to_profiles_map(data)

            return {
                "pydantic_data": data,
                "nature_lookup": nature_lookup,
                "df_profiles": df_profiles,
                "df_limits": df_limits,
                "nature_to_profiles_map": nature_to_profiles_map,
                "error": None
            }
        except ValidationError as e:
            st.error(f"❌ Fichier invalide : la structure des données est incorrecte.")
            st.code(str(e))
            return {"error": str(e)}
        except Exception as e:
            st.error(f"Une erreur critique est survenue : {e}")
            st.code(traceback.format_exc())
            return {"error": traceback.format_exc()}

def _create_profile_nature_df(data: CleemyData, nature_lookup: dict) -> pd.DataFrame:
    """Crée un DataFrame liant chaque profil aux natures qui lui sont associées."""
    export_data = []
    for profile in data.profiles:
        for id_nature in profile.idNatures:
            export_data.append({
                "Profil": profile.name_fr,
                "ID Nature": id_nature,
                "Nom de la nature": nature_lookup.get(id_nature, "❓ Inconnu"),
            })
    return pd.DataFrame(export_data)

def _create_limits_df(data: CleemyData, nature_lookup: dict) -> pd.DataFrame:
    """Crée un DataFrame consolidé de toutes les limites et indemnités de tous les profils."""
    limits_data = []
    for profile in data.profiles:
        profile_name = profile.name_fr
        for limit in profile.limits:
            nature_names = [nature_lookup.get(nid, f"ID {nid}") for nid in limit.idNatures]
            thresholds = limit.thresholds[0] if limit.thresholds else Threshold()
            limits_data.append({
                "Profil": profile_name, "Type de Règle": "Limite",
                "Natures Concernées": ", ".join(filter(None, nature_names)),
                "Type de Plafond": getattr(limit, 'type', 'N/A').capitalize(),
                "Montant": thresholds.amount,
                "Devise": limit.currencyCode,
                "Période": PERIOD_TRANSLATION.get(limit.period, limit.period)
            })
        for allowance in profile.allowances:
            nature_names = [nature_lookup.get(nid, f"ID {nid}") for nid in allowance.idNatures]
            thresholds = allowance.thresholds[0] if allowance.thresholds else Threshold()
            limits_data.append({
                "Profil": profile_name, "Type de Règle": "Indemnité",
                "Natures Concernées": ", ".join(filter(None, nature_names)),
                "Type de Plafond": "Forfait",
                "Montant": thresholds.amount,
                "Devise": allowance.currencyCode, "Période": "N/A"
            })
    return pd.DataFrame(limits_data)

def _create_nature_to_profiles_map(data: CleemyData) -> dict:
    """Crée un dictionnaire mappant chaque ID de nature aux profils et règles qui l'utilisent."""
    nature_map = {}
    for profile in data.profiles:
        for nature_id in profile.idNatures:
            nature_map.setdefault(nature_id, {}).setdefault(profile.name_fr, {"limits": [], "allowances": []})
        for limit in profile.limits:
            for nature_id in limit.idNatures:
                profile_rules = nature_map.setdefault(nature_id, {}).setdefault(profile.name_fr, {"limits": [], "allowances": []})
                profile_rules["limits"].append(limit)
        for allowance in profile.allowances:
            for nature_id in allowance.idNatures:
                profile_rules = nature_map.setdefault(nature_id, {}).setdefault(profile.name_fr, {"limits": [], "allowances": []})
                profile_rules["allowances"].append(allowance)
    return nature_map

def find_orphan_nature_ids(df_profiles: pd.DataFrame, nature_lookup: dict) -> set:
    """Trouve les ID de natures utilisés dans les profils mais non définis."""
    nature_ids_in_df = set(df_profiles["ID Nature"].unique())
    nature_ids_in_dict = set(nature_lookup.keys())
    orphans = nature_ids_in_df - nature_ids_in_dict
    return orphans

def audit_inconsistent_rules(data: CleemyData, nature_lookup: dict) -> list:
    """Trouve les règles avec des montants nuls ou non définis."""
    warnings = []
    for profile in data.profiles:
        for limit in profile.limits:
            threshold = limit.thresholds[0] if limit.thresholds else Threshold()
            if threshold.amount is None or threshold.amount == 0:
                nature_names = [nature_lookup.get(nid, f"ID {nid}") for nid in limit.idNatures]
                warnings.append(
                    f"**Profil '{profile.name_fr}'** : Limite avec montant nul ou non défini pour : *{', '.join(nature_names)}*."
                )
        for allowance in profile.allowances:
            threshold = allowance.thresholds[0] if allowance.thresholds else Threshold()
            if threshold.amount is None or threshold.amount == 0:
                nature_names = [nature_lookup.get(nid, f"ID {nid}") for nid in allowance.idNatures]
                warnings.append(
                    f"**Profil '{profile.name_fr}'** : Indemnité avec montant nul ou non défini pour : *{', '.join(nature_names)}*."
                )
    return warnings


# --- FONCTION D'ASSISTANCE POUR L'AFFICHAGE ---
def display_rule(rule: Limit | Allowance, nature_lookup: dict, show_natures: bool = True):
    """Affiche une règle (Limite ou Indemnité) de manière formatée dans Streamlit."""
    if isinstance(rule, Limit):
        thresholds = rule.thresholds[0] if rule.thresholds else Threshold()
        amount, currency = thresholds.amount, rule.currencyCode
        limit_type = getattr(rule, 'type', 'N/A').capitalize()
        period = PERIOD_TRANSLATION.get(rule.period, rule.period)
        icon, color_func = ("🛑", st.error) if limit_type == "Absolute" else ("⚠️", st.warning)
        message = f"{icon} **{limit_type}** → **{amount or 'N/A'} {currency or ''}** {period}"
        if show_natures:
            nature_names = [nature_lookup.get(nid, f"ID {nid}") for nid in rule.idNatures]
            message += f" pour : **{', '.join(nature_names)}**"
        color_func(message)

    elif isinstance(rule, Allowance):
        thresholds = rule.thresholds[0] if rule.thresholds else Threshold()
        amount, currency = thresholds.amount, rule.currencyCode
        message = f"✅ **Forfait** → **{amount or 'N/A'} {currency or ''}**"
        if show_natures:
            nature_names = [nature_lookup.get(nid, f"ID {nid}") for nid in rule.idNatures]
            message += f" pour : **{', '.join(nature_names)}**"
        st.success(message)


# --- GÉNÉRATION DU RAPPORT PDF ---
def _safe_encode(text: str) -> str:
    """Encode le texte en toute sécurité pour la police latin-1 de FPDF."""
    return str(text).encode('latin-1', 'replace').decode('latin-1')

class PDF(FPDF):
    """Classe FPDF personnalisée pour générer le rapport PDF."""
    def header(self):
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, "Rapport d'analyse de configuration Lucca NDF", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")

    def chapter_title(self, title: str):
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        self.ln(5)

    def chapter_body(self, df: pd.DataFrame):
        if df.empty:
            self.set_font("Helvetica", "", 10)
            self.multi_cell(0, 10, "Aucune donnée à afficher pour cette section.")
            self.ln()
            return
        
        num_columns = len(df.columns)
        orientation = 'L' if num_columns > 6 else 'P'
        if self.cur_orientation != orientation:
            self.add_page(orientation=orientation)
        
        effective_page_width = self.w - 2 * self.l_margin
        col_width = effective_page_width / num_columns
        
        self.set_font("Helvetica", "B", 8)
        for header in df.columns:
            self.cell(col_width, 10, _safe_encode(header), border=1, align="C")
        self.ln()
        
        self.set_font("Helvetica", "", 8)
        for _, row in df.iterrows():
            for col in df.columns:
                self.cell(col_width, 10, _safe_encode(str(row[col])), border=1)
            self.ln()
        self.ln(10)

def create_pdf_report() -> bytes:
    """Génère un rapport PDF complet à partir des données en session."""
    processed_data = st.session_state.processed_data
    pdf = PDF()
    pdf.alias_nb_pages()
    
    pdf.add_page()
    pdf.chapter_title("Vue d'ensemble des associations Profils/Natures")
    pdf.chapter_body(processed_data["df_profiles"])
    
    pdf.add_page()
    pdf.chapter_title("Analyse comparative des Limites et Indemnites")
    pdf.chapter_body(processed_data["df_limits"])
    
    orphans = find_orphan_nature_ids(processed_data["df_profiles"], processed_data["nature_lookup"])
    if orphans:
        pdf.add_page()
        pdf.chapter_title("Incoherences detectees (natures non trouvees)")
        pdf.set_font("Helvetica", "", 10)
        orphan_text = f"Les ID de natures suivants sont utilises dans des profils mais ne sont pas definis : {sorted(list(orphans))}"
        pdf.multi_cell(0, 10, _safe_encode(orphan_text))
        pdf.ln()

    return bytes(pdf.output())


# --- INTERFACES DES ONGLETS ---
def build_overview_ui():
    """Construit l'interface de l'onglet 'Vue d'Ensemble'."""
    st.header("📖 Vue d'ensemble des associations Profils/Natures")
    st.write("Utilisez la barre de recherche pour filtrer sur plusieurs mots-clés (ex: `salarié restaurant`).")
    
    processed_data = st.session_state.processed_data
    df_profiles = processed_data["df_profiles"]
    search_term = st.text_input("🔍 Rechercher sur tout le tableau")
    
    display_df = df_profiles
    if search_term:
        with st.spinner("Filtrage des données..."):
            search_space = display_df.astype(str).apply(' '.join, axis=1).str.lower()
            mask = pd.Series([True] * len(display_df), index=display_df.index)
            for term in search_term.lower().split():
                mask &= search_space.str.contains(term, na=False)
            display_df = display_df[mask]

    if display_df.empty:
        st.warning("Aucun résultat pour cette recherche.")
    else:
        st.dataframe(display_df, use_container_width=True)
        st.divider()
        st.subheader("🚀 Exports")
        st.write("Les boutons ci-dessous exporteront les données (le CSV est filtré, le PDF et l'Excel sont complets).")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            csv_data = display_df.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Télécharger en CSV", data=csv_data, file_name='rapport_profils.csv', mime='text/csv', use_container_width=True)
        with col2:
            pdf_bytes = create_pdf_report()
            st.download_button(label="📄 Télécharger en PDF", data=pdf_bytes, file_name="rapport_complet.pdf", mime="application/pdf", use_container_width=True)
        with col3:
            xlsx_output = BytesIO()
            with pd.ExcelWriter(xlsx_output, engine='openpyxl') as writer:
                display_df.to_excel(writer, index=False, sheet_name="Vue d'ensemble (filtree)")
                processed_data['df_limits'].to_excel(writer, index=False, sheet_name="Toutes les regles")
            st.download_button(
                label="📊 Télécharger en Excel (multi-feuilles)", 
                data=xlsx_output.getvalue(), 
                file_name="rapport_complet.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                use_container_width=True
            )

def build_profile_analysis_ui():
    """Construit l'interface de l'onglet 'Analyse par Profil'."""
    st.header("👤 Analyse détaillée par Profil")
    st.write("Choisissez un profil pour afficher en détail sa configuration complète.")
    
    processed_data = st.session_state.processed_data
    data = processed_data["pydantic_data"]
    nature_lookup = processed_data["nature_lookup"]
    
    profiles_dict = {p.name_fr: p for p in data.profiles}
    sorted_profiles = sorted(profiles_dict.keys())
    selected_profil_name = st.selectbox("Sélectionnez un profil", options=sorted_profiles, key="profile_select_analysis")
    
    if not selected_profil_name: return

    profile = profiles_dict[selected_profil_name]
    st.divider()
    st.subheader(f"Détails pour : {selected_profil_name}")

    st.markdown("##### Natures associées")
    nature_names = [nature_lookup.get(nid, f"ID {nid}") for nid in profile.idNatures]
    st.dataframe({"Natures": sorted(nature_names)}, use_container_width=True, hide_index=True)

    st.markdown("##### Limites de Dépenses (Plafonds)")
    if not profile.limits:
        st.info("Aucune limite spécifique n'est définie.")
    else:
        for limit in profile.limits:
            display_rule(limit, nature_lookup)

    st.markdown("##### Indemnités Forfaitaires (Allowances)")
    if not profile.allowances:
        st.info("Aucune indemnité forfaitaire n'est définie.")
    else:
        for allowance in profile.allowances:
            display_rule(allowance, nature_lookup)

def build_limits_analysis_ui():
    """Construit l'interface de l'onglet 'Analyse des Limites'."""
    st.header("📏 Analyse comparative des Limites et Indemnités")
    
    df_limits = st.session_state.processed_data["df_limits"]
    if df_limits.empty:
        st.warning("Aucune limite ou indemnité n'a été trouvée dans le fichier.")
    else:
        st.subheader("Visualisation du nombre de règles par profil")
        st.write("Ce graphique montre combien de règles (limites + indemnités) sont définies pour chaque profil.")
        rules_per_profile = df_limits["Profil"].value_counts()
        st.bar_chart(rules_per_profile)
        
        st.divider()
        st.subheader("Tableau détaillé des règles")
        st.write("Ce tableau centralise toutes les règles de tous les profils pour faciliter leur comparaison.")
        st.dataframe(df_limits, use_container_width=True)

def build_accounting_plan_ui():
    """Construit l'interface de l'onglet 'Analyse Plan Comptable'."""
    st.header("🧾 Analyse du Plan Comptable par Nature")
    st.write("Choisissez une nature pour voir son imputation comptable dans chaque plan.")
    
    data = st.session_state.processed_data["pydantic_data"]
    if not data.natures:
        st.warning("Aucune nature de dépense trouvée dans le fichier.")
        return

    natures_list = sorted([(n.name_fr, n.id) for n in data.natures])
    selected_option = st.selectbox(
        "Choisissez une nature à analyser", 
        options=natures_list, 
        format_func=lambda x: x[0], 
        key="accounting_select"
    )

    if not selected_option: return
    selected_nature_name, selected_nature_id = selected_option
    st.divider()
    
    found = False
    for chart in data.chartsOfAccounts:
        costs_accounts_lookup = {acc.id: acc.value for acc in chart.costsAccounts}
        for mapping in chart.natureAccountMappings:
            if mapping.idNature == selected_nature_id:
                found = True
                with st.expander(f"**Plan : {chart.name}**", expanded=True):
                    compte_de_charge = costs_accounts_lookup.get(mapping.idCostsAccount, 'Non trouvé')
                    st.markdown(f"**Compte de charge :** `{compte_de_charge}`")
                    st.markdown(f"**ID de TVA applicables :** `{', '.join(map(str, mapping.vat_ids)) or 'Aucun'}`")
    if not found:
        st.warning(f"La nature **{selected_nature_name}** n'est associée à aucun plan comptable.")

def build_nature_analysis_ui():
    """
    Construit l'interface de l'onglet 'Analyse par Nature'.
    Sépare les profils avec règles des profils sans règle pour un affichage plus condensé.
    """
    st.header("🔬 Analyse détaillée par Nature")
    st.write("Choisissez une nature pour voir tous les profils et les règles qui s'y appliquent.")

    processed_data = st.session_state.processed_data
    nature_lookup = processed_data["nature_lookup"]
    nature_to_profiles_map = processed_data["nature_to_profiles_map"]

    if not nature_lookup:
        st.warning("Aucune nature de dépense à analyser.")
        return

    natures_list = sorted(nature_lookup.items(), key=lambda item: item[1])
    selected_nature_id = st.selectbox(
        "Sélectionnez une nature",
        options=[n[0] for n in natures_list],
        format_func=lambda x: nature_lookup.get(x, "N/A"),
        key="nature_select_analysis"
    )
    st.divider()

    if not selected_nature_id: return

    profiles_for_nature = nature_to_profiles_map.get(selected_nature_id, {})
    if not profiles_for_nature:
        st.warning("Aucun profil n'utilise cette nature.")
        return

    st.subheader(f"Analyse pour : {nature_lookup[selected_nature_id]}")

    # --- Séparer les profils avec et sans règles ---
    profiles_with_rules = {}
    profiles_without_rules = []
    for profile_name, rules in profiles_for_nature.items():
        if rules["limits"] or rules["allowances"]:
            profiles_with_rules[profile_name] = rules
        else:
            profiles_without_rules.append(profile_name)
    
    # --- 1. Afficher les profils AVEC des règles spécifiques ---
    st.markdown("##### Profils avec règles spécifiques")
    if not profiles_with_rules:
        st.info("Aucun profil n'a de règle spécifique pour cette nature.")
    else:
        for profile_name, rules in sorted(profiles_with_rules.items()):
            with st.container(border=True):
                st.markdown(f"**{profile_name}**")
                profile_rules_data = []
                for limit in rules["limits"]:
                    threshold = limit.thresholds[0] if limit.thresholds else Threshold()
                    profile_rules_data.append({
                        "Type": "Limite", "Détail": getattr(limit, 'type', 'N/A').capitalize(),
                        "Montant": threshold.amount, "Devise": limit.currencyCode,
                        "Période": PERIOD_TRANSLATION.get(limit.period, limit.period)
                    })
                for allowance in rules["allowances"]:
                    threshold = allowance.thresholds[0] if allowance.thresholds else Threshold()
                    profile_rules_data.append({
                        "Type": "Indemnité", "Détail": "Forfait", "Montant": threshold.amount,
                        "Devise": allowance.currencyCode, "Période": "N/A"
                    })
                
                df_profile_rules = pd.DataFrame(profile_rules_data)
                st.dataframe(df_profile_rules, hide_index=True, use_container_width=True)
    
    st.divider()

    # --- 2. Afficher les profils SANS règles spécifiques ---
    st.markdown("##### Profils utilisant cette nature sans règle spécifique")
    if not profiles_without_rules:
        st.info("Tous les profils utilisant cette nature ont des règles spécifiques.")
    else:
        df_no_rules = pd.DataFrame(sorted(profiles_without_rules), columns=["Profil"])
        st.dataframe(df_no_rules, hide_index=True, use_container_width=True)


def build_comparison_ui():
    """Construit l'interface du comparateur de profils avec une analyse des différences."""
    st.header("⚖️ Comparateur de Profils")
    st.write("Sélectionnez deux profils pour afficher une analyse comparative détaillée de leurs configurations.")
    
    processed_data = st.session_state.processed_data
    df_profiles = processed_data["df_profiles"]
    df_limits = processed_data["df_limits"]
    
    all_profiles = sorted(df_profiles["Profil"].unique())
    selected_profiles = st.multiselect("Choisissez les profils à comparer", options=all_profiles, max_selections=2)

    if len(selected_profiles) != 2:
        st.info("Veuillez sélectionner exactement deux profils pour lancer la comparaison.")
        return
        
    st.divider()
    profile1_name, profile2_name = selected_profiles[0], selected_profiles[1]
    st.subheader(f"Comparaison : `{profile1_name}` vs `{profile2_name}`")

    # --- 1. Comparaison des Natures ---
    with st.expander("🕵️ **Analyse des Natures**", expanded=True):
        natures1 = set(df_profiles[df_profiles["Profil"] == profile1_name]["Nom de la nature"])
        natures2 = set(df_profiles[df_profiles["Profil"] == profile2_name]["Nom de la nature"])

        common_natures = sorted(list(natures1 & natures2))
        unique_to_1 = sorted(list(natures1 - natures2))
        unique_to_2 = sorted(list(natures2 - natures1))

        st.markdown("##### ✅ Natures Communes")
        if common_natures:
            st.dataframe({"Natures partagées": common_natures}, use_container_width=True, hide_index=True)
        else:
            st.info("Aucune nature en commun.")

        st.markdown("##### 🔍 Natures Uniques")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Uniques à `{profile1_name}`**")
            if unique_to_1:
                st.dataframe({f"Natures uniques ({len(unique_to_1)})": unique_to_1}, hide_index=True, use_container_width=True)
            else:
                st.info("Aucune.")
        with col2:
            st.markdown(f"**Uniques à `{profile2_name}`**")
            if unique_to_2:
                st.dataframe({f"Natures uniques ({len(unique_to_2)})": unique_to_2}, hide_index=True, use_container_width=True)
            else:
                st.info("Aucune.")
    
    # --- 2. Comparaison des Règles ---
    with st.expander("📏 **Analyse des Règles (Limites et Indemnités)**", expanded=True):
        rules1 = df_limits[df_limits["Profil"] == profile1_name].drop(columns='Profil')
        rules2 = df_limits[df_limits["Profil"] == profile2_name].drop(columns='Profil')

        if rules1.empty and rules2.empty:
            st.info("Aucun des deux profils n'a de règle spécifique.")
        else:
            comparison_df = pd.merge(
                rules1, rules2, 
                on=["Natures Concernées", "Type de Règle"], 
                how='outer', 
                suffixes=(f' ({profile1_name})', f' ({profile2_name})')
            )
            st.write("Ce tableau fusionne les règles. Les `NaN` indiquent une règle absente pour un profil.")
            st.dataframe(comparison_df, use_container_width=True, hide_index=True)


# --- POINT D'ENTRÉE PRINCIPAL ---
def main():
    """Point d'entrée principal de l'application Streamlit."""
    st.title("📊 Analyseur de configuration Lucca NDF")
    st.info(
        "👋 **Bienvenue !** Cet outil vous permet d'analyser et d'auditer vos profils de dépenses."
        " Chargez votre fichier `Full.json` ci-dessous pour commencer."
    )

    uploaded_file = st.file_uploader("Déposez votre fichier `Full.json` ici", type="json")

    if uploaded_file:
        # On ne retraite le fichier que s'il est nouveau pour optimiser
        if 'processed_data' not in st.session_state or st.session_state.get('uploaded_filename') != uploaded_file.name:
            st.session_state.processed_data = load_and_process_data(uploaded_file)
            st.session_state.uploaded_filename = uploaded_file.name

        processed_data = st.session_state.processed_data
        
        if processed_data and processed_data.get("error") is None:
            st.toast("Fichier validé et traité avec succès !", icon="✅")
            
            pydantic_data = processed_data["pydantic_data"]
            df_profiles = processed_data["df_profiles"]
            nature_lookup = processed_data["nature_lookup"]

            orphans = find_orphan_nature_ids(df_profiles, nature_lookup)
            if orphans:
                with st.expander("🚩 Incohérences détectées (natures non trouvées)", expanded=False):
                    st.warning(f"Les ID suivants sont présents dans des profils mais absents de la table des natures : {sorted(list(orphans))}")

            inconsistencies = audit_inconsistent_rules(pydantic_data, nature_lookup)
            if inconsistencies:
                with st.expander("⚠️ Alertes de configuration (règles à 0 ou sans montant)", expanded=True):
                    for warning_text in inconsistencies:
                        st.warning(warning_text)

            tabs_titles = [
                "📖 Vue d'Ensemble", "👤 Analyse par Profil", "🔬 Analyse par Nature",
                "📏 Analyse des Limites", "🧾 Analyse Plan Comptable", "⚖️ Comparateur de Profils"
            ]
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(tabs_titles)

            with tab1: build_overview_ui()
            with tab2: build_profile_analysis_ui()
            with tab3: build_nature_analysis_ui()
            with tab4: build_limits_analysis_ui()
            with tab5: build_accounting_plan_ui()
            with tab6: build_comparison_ui()

if __name__ == "__main__":
    main()