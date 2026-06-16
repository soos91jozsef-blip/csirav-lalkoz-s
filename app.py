import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials

# ------------------------------
# Google Sheets beállítások
# ------------------------------
SHEET_NAME = "CsíraVállalkozás"
WORKSHEETS = {
    "expenses": "Kiadasok",
    "income": "Bevetelek",
    "equipment": "Eszkozok"
}

# Oldal konfiguráció
st.set_page_config(
    page_title="Csíra Vállalkozás Követő",
    page_icon="🌱",
    layout="wide"
)

# ------------------------------
# Árfolyamok (mostantól online frissülnek)
# ------------------------------
@st.cache_data(ttl=86400)  # 24 óráig (86400 másodperc) tárolja az árfolyamokat a gyorsítótárban
def get_exchange_rates():
    """Letölti az aktuális árfolyamokat a Frankfurter API-ról (EUR alapon)."""
    try:
        url = "https://api.frankfurter.app/latest?from=EUR&to=HUF,RSD"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        rates = data['rates']
        # Az EUR árfolyama önmagában 1
        eur_to_huf = rates['HUF']
        eur_to_rsd = rates['RSD']
        
        # A szótárunk HUF alapon számol, ezért átváltjuk
        # 1 EUR = X HUF  =>  1 HUF = 1 / X EUR
        # 1 EUR = Y RSD  =>  1 RSD = 1 / Y EUR
        # 1 HUF = (1/X) * Y RSD
        return {
            'HUF': 1.0,
            'EUR': eur_to_huf,
            'RSD': eur_to_huf / eur_to_rsd
        }
    except Exception as e:
        # Hiba esetén (pl. nincs net) visszaadja a legutolsó ismert árfolyamokat
        st.warning(f"⚠️ Nem sikerült frissíteni az árfolyamokat. Az utolsó ismert értékeket használjuk. Hiba: {e}")
        return {
            'HUF': 1.0,
            'EUR': 380.0,
            'RSD': 3.25,
        }

# Pénznem szimbólumok és formátumok
CURRENCY_INFO = {
    'HUF': {'symbol': 'Ft', 'name': 'Magyar Forint'},
    'EUR': {'symbol': '€', 'name': 'Euró'},
    'RSD': {'symbol': 'din', 'name': 'Szerb Dinár'},
}

# ------------------------------
# Google Sheets kapcsolat
# ------------------------------
@st.cache_resource
def get_gsheet_client():
    """Google Sheets kliens inicializálása."""
    try:
        creds_dict = json.loads(st.secrets["gcp_credentials"])
    except (KeyError, json.JSONDecodeError):
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        return gspread.authorize(creds)
    
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def load_data():
    """Adatok betöltése a Google Sheets-ből DataFrame-ekbe."""
    client = get_gsheet_client()
    sheet = client.open(SHEET_NAME)
    
    # Kiadások
    try:
        ws_exp = sheet.worksheet(WORKSHEETS["expenses"])
        data_exp = ws_exp.get_all_records()
        expenses = pd.DataFrame(data_exp) if data_exp else pd.DataFrame(columns=['date', 'item', 'amount', 'currency', 'category'])
    except:
        expenses = pd.DataFrame(columns=['date', 'item', 'amount', 'currency', 'category'])
    
    # Bevételek
    try:
        ws_inc = sheet.worksheet(WORKSHEETS["income"])
        data_inc = ws_inc.get_all_records()
        income = pd.DataFrame(data_inc) if data_inc else pd.DataFrame(columns=['date', 'description', 'amount', 'currency'])
    except:
        income = pd.DataFrame(columns=['date', 'description', 'amount', 'currency'])
    
    # Eszközök
    try:
        ws_eq = sheet.worksheet(WORKSHEETS["equipment"])
        data_eq = ws_eq.get_all_records()
        equipment = pd.DataFrame(data_eq) if data_eq else pd.DataFrame(columns=['name', 'purchase_date', 'cost', 'currency', 'status'])
    except:
        equipment = pd.DataFrame(columns=['name', 'purchase_date', 'cost', 'currency', 'status'])
    
    return expenses, income, equipment

def save_full_data(expenses, income, equipment):
    """Teljes adatok mentése a Google Sheets-be (felülírás)."""
    client = get_gsheet_client()
    sheet = client.open(SHEET_NAME)
    
    # Kiadások
    ws_exp = sheet.worksheet(WORKSHEETS["expenses"])
    ws_exp.clear()
    if not expenses.empty:
        ws_exp.update([expenses.columns.tolist()] + expenses.values.tolist())
    else:
        ws_exp.update([['date', 'item', 'amount', 'currency', 'category']])
    
    # Bevételek
    ws_inc = sheet.worksheet(WORKSHEETS["income"])
    ws_inc.clear()
    if not income.empty:
        ws_inc.update([income.columns.tolist()] + income.values.tolist())
    else:
        ws_inc.update([['date', 'description', 'amount', 'currency']])
    
    # Eszközök
    ws_eq = sheet.worksheet(WORKSHEETS["equipment"])
    ws_eq.clear()
    if not equipment.empty:
        ws_eq.update([equipment.columns.tolist()] + equipment.values.tolist())
    else:
        ws_eq.update([['name', 'purchase_date', 'cost', 'currency', 'status']])

# Átváltás más pénznemre (mostantól az aktuális árfolyamokat használja)
def convert_currency(amount, from_currency, to_currency):
    rates = get_exchange_rates()
    amount_huf = amount * rates.get(from_currency, 1.0)
    return amount_huf / rates.get(to_currency, 1.0)

# Fő alkalmazás
def main():
    st.title("🌱 Csíra Vállalkozás Pénzügyi Követő")
    
    # Árfolyamok előzetes betöltése és kiírása (informatív jelleggel)
    rates = get_exchange_rates()
    with st.sidebar:
        st.caption(f"💱 Aktuális árfolyamok:")
        st.caption(f"1 EUR = {rates['EUR']:.2f} Ft")
        st.caption(f"100 RSD = {rates['RSD']*100:.2f} Ft")
    
    # Session state inicializálása
    if 'expenses' not in st.session_state:
        st.session_state.expenses, st.session_state.income, st.session_state.equipment = load_data()
    if 'edit_expense_index' not in st.session_state:
        st.session_state.edit_expense_index = None
    if 'edit_income_index' not in st.session_state:
        st.session_state.edit_income_index = None
    if 'edit_equipment_index' not in st.session_state:
        st.session_state.edit_equipment_index = None
    
    expenses = st.session_state.expenses
    income = st.session_state.income
    equipment = st.session_state.equipment
    
    menu = st.sidebar.selectbox(
        "Menü",
        ["📊 Áttekintés", "💰 Kiadások", "💵 Bevételek", "🛠️ Eszközök", "📈 Részletes Statisztika"]
    )
    
    if menu in ["📊 Áttekintés", "📈 Részletes Statisztika"]:
        st.sidebar.markdown("---")
        display_currency = st.sidebar.selectbox(
            "📌 Statisztika pénzneme:",
            ['HUF', 'EUR', 'RSD'],
            help="Válaszd ki, milyen pénznemben szeretnéd látni a statisztikákat"
        )
    else:
        display_currency = 'HUF'
    
    if menu == "📊 Áttekintés":
        show_overview(expenses, income, display_currency)
    elif menu == "💰 Kiadások":
        show_expenses(expenses)
    elif menu == "💵 Bevételek":
        show_income(income)
    elif menu == "🛠️ Eszközök":
        show_equipment(equipment, display_currency)
    elif menu == "📈 Részletes Statisztika":
        show_detailed_stats(expenses, income, display_currency)

def show_overview(expenses, income, display_currency):
    st.header("📊 Pénzügyi Áttekintés")
    symbol = CURRENCY_INFO[display_currency]['symbol']
    
    total_expenses = 0
    if not expenses.empty:
        for _, row in expenses.iterrows():
            total_expenses += convert_currency(row['amount'], row['currency'], display_currency)
    
    total_income = 0
    if not income.empty:
        for _, row in income.iterrows():
            total_income += convert_currency(row['amount'], row['currency'], display_currency)
    
    profit = total_income - total_expenses
    profit_margin = (profit / total_income * 100) if total_income > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📤 Összes Kiadás", f"{total_expenses:,.0f} {symbol}", delta_color="inverse")
    with col2:
        st.metric("📥 Összes Bevétel", f"{total_income:,.0f} {symbol}", delta_color="normal")
    with col3:
        st.metric("💰 Haszon", f"{profit:,.0f} {symbol}", delta=f"{profit_margin:.1f}%", delta_color="normal" if profit >= 0 else "inverse")
    with col4:
        st.metric("📈 Haszonkulcs", f"{profit_margin:.1f}%")
    
    st.subheader("📊 Kiadás, Bevétel, Haszon Összehasonlítás")
    fig = go.Figure(data=[
        go.Bar(name='Kiadás', x=['Pénzügyi összesítő'], y=[total_expenses], marker=dict(color='#FF4444', line=dict(color='#CC0000', width=2)), text=[f"{total_expenses:,.0f} {symbol}"], textposition='auto'),
        go.Bar(name='Bevétel', x=['Pénzügyi összesítő'], y=[total_income], marker=dict(color='#4CAF50', line=dict(color='#2E7D32', width=2)), text=[f"{total_income:,.0f} {symbol}"], textposition='auto'),
        go.Bar(name='Haszon', x=['Pénzügyi összesítő'], y=[profit], marker=dict(color='#2196F3' if profit >= 0 else '#FF9800', line=dict(color='#1565C0' if profit >= 0 else '#E65100', width=2)), text=[f"{profit:,.0f} {symbol}"], textposition='auto')
    ])
    fig.update_layout(title={'text': f'Pénzügyi Összesítő ({CURRENCY_INFO[display_currency]["name"]})', 'font': {'size': 20}}, barmode='group', plot_bgcolor='rgba(240,240,240,0.8)', height=500)
    st.plotly_chart(fig, width='stretch')
    
    col1, col2 = st.columns(2)
    with col1:
        if not expenses.empty:
            expenses_copy = expenses.copy()
            expenses_copy['amount_converted'] = expenses_copy.apply(lambda row: convert_currency(row['amount'], row['currency'], display_currency), axis=1)
            expenses_by_category = expenses_copy.groupby('category')['amount_converted'].sum().reset_index()
            st.subheader("📋 Kiadások Kategóriánként")
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD']
            fig = px.pie(expenses_by_category, values='amount_converted', names='category', color_discrete_sequence=colors)
            fig.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='white', width=2)))
            fig.update_layout(height=400)
            st.plotly_chart(fig, width='stretch')
    with col2:
        if not income.empty and not expenses.empty:
            st.subheader("💡 Pénzügyi Mutatók")
            fig = go.Figure(go.Indicator(mode="gauge+number+delta", value=profit_margin, domain={'x': [0,1], 'y': [0,1]}, title={'text': "Haszonkulcs %"}, delta={'reference': 20}, gauge={'axis': {'range': [None, 100]}, 'bar': {'color': "#4CAF50" if profit_margin >= 20 else "#FFA726"}, 'steps': [{'range': [0,10], 'color': "#ffcccc"}, {'range': [10,30], 'color': "#ffffcc"}, {'range': [30,100], 'color': "#ccffcc"}], 'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 20}}))
            fig.update_layout(height=350)
            st.plotly_chart(fig, width='stretch')

def show_expenses(expenses):
    st.header("💰 Kiadások Kezelése")
    
    # Szerkesztési állapot kezelése
    if st.session_state.edit_expense_index is not None:
        idx = st.session_state.edit_expense_index
        if idx < len(expenses):
            row = expenses.iloc[idx]
            st.subheader("✏️ Kiadás szerkesztése")
            with st.form("edit_expense_form"):
                col1, col2, col3, col4 = st.columns([2,2,2,2])
                with col1:
                    date = st.date_input("Dátum", pd.to_datetime(row['date']))
                with col2:
                    item = st.text_input("Megnevezés", value=row['item'])
                with col3:
                    amount = st.number_input("Összeg", value=float(row['amount']), min_value=0.0, step=100.0, format="%.0f")
                with col4:
                    currency = st.selectbox("Pénznem", ['HUF', 'EUR', 'RSD'], index=['HUF','EUR','RSD'].index(row['currency']))
                category = st.selectbox("Kategória", 
                    ["Anyagköltség", "Eszközök", "Szállítás", "Csomagolás", "Marketing", "Egyéb"],
                    index=["Anyagköltség", "Eszközök", "Szállítás", "Csomagolás", "Marketing", "Egyéb"].index(row['category']))
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.form_submit_button("💾 Módosítás mentése", use_container_width=True):
                        # Adatok frissítése
                        expenses.at[idx, 'date'] = date.strftime('%Y-%m-%d')
                        expenses.at[idx, 'item'] = item
                        expenses.at[idx, 'amount'] = amount
                        expenses.at[idx, 'currency'] = currency
                        expenses.at[idx, 'category'] = category
                        st.session_state.expenses = expenses
                        save_full_data(expenses, st.session_state.income, st.session_state.equipment)
                        st.session_state.edit_expense_index = None
                        st.success("✅ Kiadás módosítva!")
                        st.rerun()
                with col_btn2:
                    if st.form_submit_button("❌ Mégsem", use_container_width=True):
                        st.session_state.edit_expense_index = None
                        st.rerun()
    
    # Új kiadás hozzáadása
    with st.expander("➕ Új Kiadás Hozzáadása", expanded=(st.session_state.edit_expense_index is None)):
        col1, col2, col3, col4 = st.columns([2,2,2,2])
        with col1: date_new = st.date_input("Dátum", datetime.now(), key="new_exp_date")
        with col2: item_new = st.text_input("Megnevezés", placeholder="pl. Csíra magvak", key="new_exp_item")
        with col3: amount_new = st.number_input("Összeg", min_value=0.0, step=100.0, format="%.0f", key="new_exp_amount")
        with col4: currency_new = st.selectbox("Pénznem", ['HUF', 'EUR', 'RSD'], key="new_exp_currency")
        category_new = st.selectbox("Kategória", 
            ["Anyagköltség", "Eszközök", "Szállítás", "Csomagolás", "Marketing", "Egyéb"], key="new_exp_category")
        if st.button("💾 Kiadás Mentése", type="primary", use_container_width=True, key="save_new_expense"):
            if item_new and amount_new > 0:
                new_row = pd.DataFrame({'date': [date_new.strftime('%Y-%m-%d')], 'item': [item_new], 'amount': [amount_new], 'currency': [currency_new], 'category': [category_new]})
                expenses = pd.concat([expenses, new_row], ignore_index=True)
                st.session_state.expenses = expenses
                save_full_data(expenses, st.session_state.income, st.session_state.equipment)
                st.success(f"✅ Kiadás mentve: {item_new} - {amount_new:,.0f} {CURRENCY_INFO[currency_new]['symbol']}")
                st.rerun()
            else:
                st.error("❌ Kérlek tölts ki minden mezőt!")
    
    # Meglévő kiadások listája
    if not expenses.empty:
        st.subheader("📋 Kiadások Listája")
        for i, (idx, row) in enumerate(expenses.iterrows()):
            cols = st.columns([1.5, 2.5, 1.5, 1.5, 1.5, 1.5, 1.5])
            cols[0].write(row['date'])
            cols[1].write(row['item'])
            cols[2].write(f"{row['amount']:,.0f} {CURRENCY_INFO[row['currency']]['symbol']}")
            cols[3].write(f"{convert_currency(row['amount'], row['currency'], 'HUF'):,.0f} Ft")
            cols[4].write(row['category'])
            if cols[5].button("✏️", key=f"edit_exp_{i}"):
                st.session_state.edit_expense_index = i
                st.rerun()
            if cols[6].button("🗑️", key=f"del_exp_{i}"):
                expenses = expenses.drop(idx).reset_index(drop=True)
                st.session_state.expenses = expenses
                save_full_data(expenses, st.session_state.income, st.session_state.equipment)
                st.success("✅ Kiadás törölve!")
                st.rerun()
        
        total_huf = sum(convert_currency(row['amount'], row['currency'], 'HUF') for _, row in expenses.iterrows())
        st.info(f"📤 **Összes kiadás:** {total_huf:,.0f} Ft")

def show_income(income):
    st.header("💵 Bevételek Kezelése")
    
    # Szerkesztési állapot
    if st.session_state.edit_income_index is not None:
        idx = st.session_state.edit_income_index
        if idx < len(income):
            row = income.iloc[idx]
            st.subheader("✏️ Bevétel szerkesztése")
            with st.form("edit_income_form"):
                col1, col2, col3, col4 = st.columns([2,2,2,2])
                with col1:
                    date = st.date_input("Dátum", pd.to_datetime(row['date']))
                with col2:
                    desc = st.text_input("Megnevezés", value=row['description'])
                with col3:
                    amount = st.number_input("Összeg", value=float(row['amount']), min_value=0.0, step=100.0, format="%.0f")
                with col4:
                    currency = st.selectbox("Pénznem", ['HUF', 'EUR', 'RSD'], index=['HUF','EUR','RSD'].index(row['currency']))
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.form_submit_button("💾 Módosítás mentése", use_container_width=True):
                        income.at[idx, 'date'] = date.strftime('%Y-%m-%d')
                        income.at[idx, 'description'] = desc
                        income.at[idx, 'amount'] = amount
                        income.at[idx, 'currency'] = currency
                        st.session_state.income = income
                        save_full_data(st.session_state.expenses, income, st.session_state.equipment)
                        st.session_state.edit_income_index = None
                        st.success("✅ Bevétel módosítva!")
                        st.rerun()
                with col_btn2:
                    if st.form_submit_button("❌ Mégsem", use_container_width=True):
                        st.session_state.edit_income_index = None
                        st.rerun()
    
    # Új bevétel
    with st.expander("➕ Új Bevétel Hozzáadása", expanded=(st.session_state.edit_income_index is None)):
        col1, col2, col3, col4 = st.columns([2,2,2,2])
        with col1: date_new = st.date_input("Dátum", datetime.now(), key="new_inc_date")
        with col2: desc_new = st.text_input("Megnevezés", placeholder="pl. Brokkoli csíra eladás", key="new_inc_desc")
        with col3: amount_new = st.number_input("Összeg", min_value=0.0, step=100.0, format="%.0f", key="new_inc_amount")
        with col4: currency_new = st.selectbox("Pénznem", ['HUF', 'EUR', 'RSD'], key="new_inc_currency")
        if st.button("💾 Bevétel Mentése", type="primary", use_container_width=True, key="save_new_income"):
            if desc_new and amount_new > 0:
                new_row = pd.DataFrame({'date': [date_new.strftime('%Y-%m-%d')], 'description': [desc_new], 'amount': [amount_new], 'currency': [currency_new]})
                income = pd.concat([income, new_row], ignore_index=True)
                st.session_state.income = income
                save_full_data(st.session_state.expenses, income, st.session_state.equipment)
                st.success(f"✅ Bevétel mentve: {desc_new} - {amount_new:,.0f} {CURRENCY_INFO[currency_new]['symbol']}")
                st.rerun()
            else:
                st.error("❌ Kérlek tölts ki minden mezőt!")
    
    # Lista
    if not income.empty:
        st.subheader("📋 Bevételek Listája")
        for i, (idx, row) in enumerate(income.iterrows()):
            cols = st.columns([1.5, 2.5, 1.5, 1.5, 1.5, 1.5])
            cols[0].write(row['date'])
            cols[1].write(row['description'])
            cols[2].write(f"{row['amount']:,.0f} {CURRENCY_INFO[row['currency']]['symbol']}")
            cols[3].write(f"{convert_currency(row['amount'], row['currency'], 'HUF'):,.0f} Ft")
            if cols[4].button("✏️", key=f"edit_inc_{i}"):
                st.session_state.edit_income_index = i
                st.rerun()
            if cols[5].button("🗑️", key=f"del_inc_{i}"):
                income = income.drop(idx).reset_index(drop=True)
                st.session_state.income = income
                save_full_data(st.session_state.expenses, income, st.session_state.equipment)
                st.success("✅ Bevétel törölve!")
                st.rerun()
        
        total_huf = sum(convert_currency(row['amount'], row['currency'], 'HUF') for _, row in income.iterrows())
        st.info(f"📥 **Összes bevétel:** {total_huf:,.0f} Ft")

def show_equipment(equipment, display_currency):
    st.header("🛠️ Eszközök Kezelése")
    
    # Szerkesztés
    if st.session_state.edit_equipment_index is not None:
        idx = st.session_state.edit_equipment_index
        if idx < len(equipment):
            row = equipment.iloc[idx]
            st.subheader("✏️ Eszköz szerkesztése")
            with st.form("edit_equipment_form"):
                col1, col2, col3, col4 = st.columns([2,2,2,2])
                with col1:
                    name = st.text_input("Eszköz neve", value=row['name'])
                with col2:
                    purch_date = st.date_input("Beszerzés dátuma", pd.to_datetime(row['purchase_date']))
                with col3:
                    cost = st.number_input("Költség", value=float(row['cost']), min_value=0.0, step=100.0, format="%.0f")
                with col4:
                    currency = st.selectbox("Pénznem", ['HUF', 'EUR', 'RSD'], index=['HUF','EUR','RSD'].index(row['currency']))
                status = st.selectbox("Állapot", ["Aktív", "Javítás alatt", "Selejtezve"], index=["Aktív", "Javítás alatt", "Selejtezve"].index(row['status']))
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.form_submit_button("💾 Módosítás mentése", use_container_width=True):
                        equipment.at[idx, 'name'] = name
                        equipment.at[idx, 'purchase_date'] = purch_date.strftime('%Y-%m-%d')
                        equipment.at[idx, 'cost'] = cost
                        equipment.at[idx, 'currency'] = currency
                        equipment.at[idx, 'status'] = status
                        st.session_state.equipment = equipment
                        save_full_data(st.session_state.expenses, st.session_state.income, equipment)
                        st.session_state.edit_equipment_index = None
                        st.success("✅ Eszköz módosítva!")
                        st.rerun()
                with col_btn2:
                    if st.form_submit_button("❌ Mégsem", use_container_width=True):
                        st.session_state.edit_equipment_index = None
                        st.rerun()
    
    # Új eszköz
    with st.expander("➕ Új Eszköz Hozzáadása", expanded=(st.session_state.edit_equipment_index is None)):
        col1, col2, col3, col4 = st.columns([2,2,2,2])
        with col1: name_new = st.text_input("Eszköz neve", placeholder="pl. Csíráztató tálca", key="new_eq_name")
        with col2: purch_date_new = st.date_input("Beszerzés dátuma", datetime.now(), key="new_eq_date")
        with col3: cost_new = st.number_input("Költség", min_value=0.0, step=100.0, format="%.0f", key="new_eq_cost")
        with col4: currency_new = st.selectbox("Pénznem", ['HUF', 'EUR', 'RSD'], key="new_eq_currency")
        status_new = st.selectbox("Állapot", ["Aktív", "Javítás alatt", "Selejtezve"], key="new_eq_status")
        if st.button("💾 Eszköz Mentése", type="primary", use_container_width=True, key="save_new_equipment"):
            if name_new and cost_new > 0:
                new_row = pd.DataFrame({'name': [name_new], 'purchase_date': [purch_date_new.strftime('%Y-%m-%d')], 'cost': [cost_new], 'currency': [currency_new], 'status': [status_new]})
                equipment = pd.concat([equipment, new_row], ignore_index=True)
                st.session_state.equipment = equipment
                save_full_data(st.session_state.expenses, st.session_state.income, equipment)
                st.success(f"✅ Eszköz mentve: {name_new} - {cost_new:,.0f} {CURRENCY_INFO[currency_new]['symbol']}")
                st.rerun()
            else:
                st.error("❌ Kérlek tölts ki minden mezőt!")
    
    # Lista
    if not equipment.empty:
        st.subheader("📋 Eszközök Listája")
        for i, (idx, row) in enumerate(equipment.iterrows()):
            cols = st.columns([2, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5])
            cols[0].write(row['name'])
            cols[1].write(row['purchase_date'])
            cols[2].write(f"{row['cost']:,.0f} {CURRENCY_INFO[row['currency']]['symbol']}")
            cols[3].write(f"{convert_currency(row['cost'], row['currency'], 'HUF'):,.0f} Ft")
            cols[4].write(row['status'])
            if cols[5].button("✏️", key=f"edit_eq_{i}"):
                st.session_state.edit_equipment_index = i
                st.rerun()
            if cols[6].button("🗑️", key=f"del_eq_{i}"):
                equipment = equipment.drop(idx).reset_index(drop=True)
                st.session_state.equipment = equipment
                save_full_data(st.session_state.expenses, st.session_state.income, equipment)
                st.success("✅ Eszköz törölve!")
                st.rerun()

def show_detailed_stats(expenses, income, display_currency):
    st.header("📈 Részletes Statisztika")
    symbol = CURRENCY_INFO[display_currency]['symbol']
    if not expenses.empty or not income.empty:
        st.subheader(f"📅 Havi Összesítés ({CURRENCY_INFO[display_currency]['name']})")
        if not expenses.empty:
            expenses['date'] = pd.to_datetime(expenses['date'])
            expenses['amount_converted'] = expenses.apply(lambda row: convert_currency(row['amount'], row['currency'], display_currency), axis=1)
            expenses['month'] = expenses['date'].dt.strftime('%Y-%m')
            monthly_expenses = expenses.groupby('month')['amount_converted'].sum()
        if not income.empty:
            income['date'] = pd.to_datetime(income['date'])
            income['amount_converted'] = income.apply(lambda row: convert_currency(row['amount'], row['currency'], display_currency), axis=1)
            income['month'] = income['date'].dt.strftime('%Y-%m')
            monthly_income = income.groupby('month')['amount_converted'].sum()
        all_months = []
        if not expenses.empty: all_months.extend(expenses['month'].unique())
        if not income.empty: all_months.extend(income['month'].unique())
        all_months = sorted(set(all_months))
        monthly_data = []
        for month in all_months:
            exp = monthly_expenses.get(month, 0) if not expenses.empty else 0
            inc = monthly_income.get(month, 0) if not income.empty else 0
            profit = inc - exp
            margin = (profit / inc * 100) if inc > 0 else 0
            monthly_data.append({'Hónap': month, f'Kiadás ({symbol})': round(exp,2), f'Bevétel ({symbol})': round(inc,2), f'Haszon ({symbol})': round(profit,2), 'Haszonkulcs (%)': round(margin,1)})
        if monthly_data:
            monthly_df = pd.DataFrame(monthly_data)
            st.subheader("📋 Havi Bontás Táblázat")
            st.dataframe(monthly_df, width='stretch', hide_index=True)
            st.subheader("📈 Havi Pénzügyi Trend")
            fig = go.Figure()
            fig.add_trace(go.Bar(name='Kiadás', x=monthly_df['Hónap'], y=monthly_df[f'Kiadás ({symbol})'], marker=dict(color='#FF6B6B', line=dict(color='#FF4444', width=1.5)), text=[f"{x:,.0f} {symbol}" for x in monthly_df[f'Kiadás ({symbol})']], textposition='inside'))
            fig.add_trace(go.Bar(name='Bevétel', x=monthly_df['Hónap'], y=monthly_df[f'Bevétel ({symbol})'], marker=dict(color='#51CF66', line=dict(color='#2F9E44', width=1.5)), text=[f"{x:,.0f} {symbol}" for x in monthly_df[f'Bevétel ({symbol})']], textposition='inside'))
            fig.add_trace(go.Bar(name='Haszon', x=monthly_df['Hónap'], y=monthly_df[f'Haszon ({symbol})'], marker=dict(color=['#339AF0' if x >= 0 else '#FF922B' for x in monthly_df[f'Haszon ({symbol})']], line=dict(color=['#1971C2' if x >= 0 else '#E8590C' for x in monthly_df[f'Haszon ({symbol})']], width=1.5)), text=[f"{x:,.0f} {symbol}" for x in monthly_df[f'Haszon ({symbol})']], textposition='inside'))
            fig.add_trace(go.Scatter(name='Haszonkulcs %', x=monthly_df['Hónap'], y=monthly_df['Haszonkulcs (%)'], mode='lines+markers', yaxis='y2', line=dict(color='#845EF7', width=3), marker=dict(size=10, color='#845EF7', line=dict(color='white', width=2))))
            fig.update_layout(title={'text': f'Havi Pénzügyi Kimutatás ({CURRENCY_INFO[display_currency]["name"]})', 'font': {'size': 20}}, barmode='group', plot_bgcolor='rgba(248,249,250,1)', height=550, xaxis=dict(title='Hónap'), yaxis=dict(title=f'Összeg ({symbol})'), yaxis2=dict(title='Haszonkulcs (%)', overlaying='y', side='right', range=[0,100]), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig, width='stretch')
            st.subheader("🌊 Havi Haszon Alakulása")
            fig_waterfall = go.Figure(go.Waterfall(name="Haszon", orientation="v", x=monthly_df['Hónap'], y=monthly_df[f'Haszon ({symbol})'], text=[f"{x:,.0f} {symbol}" for x in monthly_df[f'Haszon ({symbol})']], textposition="outside", connector={"line":{"color":"rgb(63,63,63)"}}, decreasing={"marker":{"color":"#FF6B6B"}}, increasing={"marker":{"color":"#51CF66"}}, totals={"marker":{"color":"#339AF0"}}))
            fig_waterfall.update_layout(title=f"Havi Haszon Változása ({symbol})", height=400, plot_bgcolor='rgba(248,249,250,1)')
            st.plotly_chart(fig_waterfall, width='stretch')
    else:
        st.info("ℹ️ Nincs még rögzített adat. Adj hozzá kiadásokat és bevételeket a megfelelő menüpontokban!")

if __name__ == "__main__":
    main()
