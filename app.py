import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# Oldal konfiguráció
st.set_page_config(
    page_title="Csíra Vállalkozás Követő",
    page_icon="🌱",
    layout="wide"
)

# Árfolyamok
EXCHANGE_RATES = {
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

# Adatok betöltése
def load_data():
    if os.path.exists('expenses.csv'):
        expenses = pd.read_csv('expenses.csv')
    else:
        expenses = pd.DataFrame(columns=['date', 'item', 'amount', 'currency', 'category'])
    
    if os.path.exists('income.csv'):
        income = pd.read_csv('income.csv')
    else:
        income = pd.DataFrame(columns=['date', 'description', 'amount', 'currency'])
    
    if os.path.exists('equipment.csv'):
        equipment = pd.read_csv('equipment.csv')
    else:
        equipment = pd.DataFrame(columns=['name', 'purchase_date', 'cost', 'currency', 'status'])
    
    return expenses, income, equipment

# Adatok mentése
def save_data(expenses, income, equipment):
    expenses.to_csv('expenses.csv', index=False)
    income.to_csv('income.csv', index=False)
    equipment.to_csv('equipment.csv', index=False)

# Átváltás más pénznemre
def convert_currency(amount, from_currency, to_currency):
    amount_huf = amount * EXCHANGE_RATES.get(from_currency, 1.0)
    return amount_huf / EXCHANGE_RATES.get(to_currency, 1.0)

# Fő alkalmazás
def main():
    st.title("🌱 Csíra Vállalkozás Pénzügyi Követő")
    
    expenses, income, equipment = load_data()
    
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
        expenses = show_expenses(expenses)
    elif menu == "💵 Bevételek":
        income = show_income(income)
    elif menu == "🛠️ Eszközök":
        equipment = show_equipment(equipment, display_currency)
    elif menu == "📈 Részletes Statisztika":
        show_detailed_stats(expenses, income, display_currency)
    
    save_data(expenses, income, equipment)

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
    st.plotly_chart(fig, use_container_width=True)
    
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
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        if not income.empty and not expenses.empty:
            st.subheader("💡 Pénzügyi Mutatók")
            roi = (profit / total_expenses * 100) if total_expenses > 0 else 0
            fig = go.Figure(go.Indicator(mode="gauge+number+delta", value=profit_margin, domain={'x': [0,1], 'y': [0,1]}, title={'text': "Haszonkulcs %"}, delta={'reference': 20}, gauge={'axis': {'range': [None, 100]}, 'bar': {'color': "#4CAF50" if profit_margin >= 20 else "#FFA726"}, 'steps': [{'range': [0,10], 'color': "#ffcccc"}, {'range': [10,30], 'color': "#ffffcc"}, {'range': [30,100], 'color': "#ccffcc"}], 'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 20}}))
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

def show_expenses(expenses):
    st.header("💰 Kiadások Kezelése")
    with st.expander("➕ Új Kiadás Hozzáadása", expanded=True):
        col1, col2, col3, col4 = st.columns([2,2,2,2])
        with col1: date = st.date_input("Dátum", datetime.now())
        with col2: item = st.text_input("Megnevezés", placeholder="pl. Csíra magvak")
        with col3: amount = st.number_input("Összeg", min_value=0.0, step=100.0, format="%.0f")
        with col4: currency = st.selectbox("Pénznem", ['HUF', 'EUR', 'RSD'])
        category = st.selectbox("Kategória", ["Anyagköltség", "Eszközök", "Szállítás", "Csomagolás", "Marketing", "Egyéb"])
        if st.button("💾 Kiadás Mentése", type="primary", use_container_width=True):
            if item and amount > 0:
                new_expense = pd.DataFrame({'date': [date.strftime('%Y-%m-%d')], 'item': [item], 'amount': [amount], 'currency': [currency], 'category': [category]})
                expenses = pd.concat([expenses, new_expense], ignore_index=True)
                st.success(f"✅ Kiadás mentve: {item} - {amount:,.0f} {CURRENCY_INFO[currency]['symbol']}")
                st.rerun()
            else:
                st.error("❌ Kérlek tölts ki minden mezőt!")
    if not expenses.empty:
        st.subheader("📋 Kiadások Listája")
        display_expenses = expenses.copy()
        display_expenses['Dátum'] = display_expenses['date']
        display_expenses['Megnevezés'] = display_expenses['item']
        display_expenses['Összeg (Eredeti)'] = display_expenses.apply(lambda row: f"{row['amount']:,.0f} {CURRENCY_INFO[row['currency']]['symbol']}", axis=1)
        display_expenses['Összeg (HUF)'] = display_expenses.apply(lambda row: f"{convert_currency(row['amount'], row['currency'], 'HUF'):,.0f} Ft", axis=1)
        display_expenses['Kategória'] = display_expenses['category']
        st.dataframe(display_expenses[['Dátum', 'Megnevezés', 'Összeg (Eredeti)', 'Összeg (HUF)', 'Kategória']], use_container_width=True, hide_index=True)
        total_huf = sum(convert_currency(row['amount'], row['currency'], 'HUF') for _, row in expenses.iterrows())
        st.info(f"📤 **Összes kiadás:** {total_huf:,.0f} Ft")
    return expenses

def show_income(income):
    st.header("💵 Bevételek Kezelése")
    with st.expander("➕ Új Bevétel Hozzáadása", expanded=True):
        col1, col2, col3, col4 = st.columns([2,2,2,2])
        with col1: date = st.date_input("Dátum", datetime.now())
        with col2: description = st.text_input("Megnevezés", placeholder="pl. Brokkoli csíra eladás")
        with col3: amount = st.number_input("Összeg", min_value=0.0, step=100.0, format="%.0f")
        with col4: currency = st.selectbox("Pénznem", ['HUF', 'EUR', 'RSD'], key="income_currency")
        if st.button("💾 Bevétel Mentése", type="primary", use_container_width=True):
            if description and amount > 0:
                new_income = pd.DataFrame({'date': [date.strftime('%Y-%m-%d')], 'description': [description], 'amount': [amount], 'currency': [currency]})
                income = pd.concat([income, new_income], ignore_index=True)
                st.success(f"✅ Bevétel mentve: {description} - {amount:,.0f} {CURRENCY_INFO[currency]['symbol']}")
                st.rerun()
            else:
                st.error("❌ Kérlek tölts ki minden mezőt!")
    if not income.empty:
        st.subheader("📋 Bevételek Listája")
        display_income = income.copy()
        display_income['Dátum'] = display_income['date']
        display_income['Megnevezés'] = display_income['description']
        display_income['Összeg (Eredeti)'] = display_income.apply(lambda row: f"{row['amount']:,.0f} {CURRENCY_INFO[row['currency']]['symbol']}", axis=1)
        display_income['Összeg (HUF)'] = display_income.apply(lambda row: f"{convert_currency(row['amount'], row['currency'], 'HUF'):,.0f} Ft", axis=1)
        st.dataframe(display_income[['Dátum', 'Megnevezés', 'Összeg (Eredeti)', 'Összeg (HUF)']], use_container_width=True, hide_index=True)
        total_huf = sum(convert_currency(row['amount'], row['currency'], 'HUF') for _, row in income.iterrows())
        st.info(f"📥 **Összes bevétel:** {total_huf:,.0f} Ft")
    return income

def show_equipment(equipment, display_currency):
    st.header("🛠️ Eszközök Kezelése")
    with st.expander("➕ Új Eszköz Hozzáadása", expanded=True):
        col1, col2, col3, col4 = st.columns([2,2,2,2])
        with col1: name = st.text_input("Eszköz neve", placeholder="pl. Csíráztató tálca")
        with col2: purchase_date = st.date_input("Beszerzés dátuma", datetime.now())
        with col3: cost = st.number_input("Költség", min_value=0.0, step=100.0, format="%.0f")
        with col4: currency = st.selectbox("Pénznem", ['HUF', 'EUR', 'RSD'], key="equipment_currency")
        status = st.selectbox("Állapot", ["Aktív", "Javítás alatt", "Selejtezve"])
        if st.button("💾 Eszköz Mentése", type="primary", use_container_width=True):
            if name and cost > 0:
                new_equipment = pd.DataFrame({'name': [name], 'purchase_date': [purchase_date.strftime('%Y-%m-%d')], 'cost': [cost], 'currency': [currency], 'status': [status]})
                equipment = pd.concat([equipment, new_equipment], ignore_index=True)
                st.success(f"✅ Eszköz mentve: {name} - {cost:,.0f} {CURRENCY_INFO[currency]['symbol']}")
                st.rerun()
            else:
                st.error("❌ Kérlek tölts ki minden mezőt!")
    if not equipment.empty:
        st.subheader("📋 Eszközök Listája")
        display_equipment = equipment.copy()
        display_equipment['Név'] = display_equipment['name']
        display_equipment['Beszerzés dátuma'] = display_equipment['purchase_date']
        display_equipment['Költség (Eredeti)'] = display_equipment.apply(lambda row: f"{row['cost']:,.0f} {CURRENCY_INFO[row['currency']]['symbol']}", axis=1)
        display_equipment['Költség (HUF)'] = display_equipment.apply(lambda row: f"{convert_currency(row['cost'], row['currency'], 'HUF'):,.0f} Ft", axis=1)
        display_equipment['Állapot'] = display_equipment['status']
        st.dataframe(display_equipment[['Név', 'Beszerzés dátuma', 'Költség (Eredeti)', 'Költség (HUF)', 'Állapot']], use_container_width=True, hide_index=True)
    return equipment

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
            st.dataframe(monthly_df, use_container_width=True, hide_index=True)
            st.subheader("📈 Havi Pénzügyi Trend")
            fig = go.Figure()
            fig.add_trace(go.Bar(name='Kiadás', x=monthly_df['Hónap'], y=monthly_df[f'Kiadás ({symbol})'], marker=dict(color='#FF6B6B', line=dict(color='#FF4444', width=1.5)), text=[f"{x:,.0f} {symbol}" for x in monthly_df[f'Kiadás ({symbol})']], textposition='inside'))
            fig.add_trace(go.Bar(name='Bevétel', x=monthly_df['Hónap'], y=monthly_df[f'Bevétel ({symbol})'], marker=dict(color='#51CF66', line=dict(color='#2F9E44', width=1.5)), text=[f"{x:,.0f} {symbol}" for x in monthly_df[f'Bevétel ({symbol})']], textposition='inside'))
            fig.add_trace(go.Bar(name='Haszon', x=monthly_df['Hónap'], y=monthly_df[f'Haszon ({symbol})'], marker=dict(color=['#339AF0' if x >= 0 else '#FF922B' for x in monthly_df[f'Haszon ({symbol})']], line=dict(color=['#1971C2' if x >= 0 else '#E8590C' for x in monthly_df[f'Haszon ({symbol})']], width=1.5)), text=[f"{x:,.0f} {symbol}" for x in monthly_df[f'Haszon ({symbol})']], textposition='inside'))
            fig.add_trace(go.Scatter(name='Haszonkulcs %', x=monthly_df['Hónap'], y=monthly_df['Haszonkulcs (%)'], mode='lines+markers', yaxis='y2', line=dict(color='#845EF7', width=3), marker=dict(size=10, color='#845EF7', line=dict(color='white', width=2))))
            fig.update_layout(title={'text': f'Havi Pénzügyi Kimutatás ({CURRENCY_INFO[display_currency]["name"]})', 'font': {'size': 20}}, barmode='group', plot_bgcolor='rgba(248,249,250,1)', height=550, xaxis=dict(title='Hónap'), yaxis=dict(title=f'Összeg ({symbol})'), yaxis2=dict(title='Haszonkulcs (%)', overlaying='y', side='right', range=[0,100]), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig, use_container_width=True)
            st.subheader("🌊 Havi Haszon Alakulása")
            fig_waterfall = go.Figure(go.Waterfall(name="Haszon", orientation="v", x=monthly_df['Hónap'], y=monthly_df[f'Haszon ({symbol})'], text=[f"{x:,.0f} {symbol}" for x in monthly_df[f'Haszon ({symbol})']], textposition="outside", connector={"line":{"color":"rgb(63,63,63)"}}, decreasing={"marker":{"color":"#FF6B6B"}}, increasing={"marker":{"color":"#51CF66"}}, totals={"marker":{"color":"#339AF0"}}))
            fig_waterfall.update_layout(title=f"Havi Haszon Változása ({symbol})", height=400, plot_bgcolor='rgba(248,249,250,1)')
            st.plotly_chart(fig_waterfall, use_container_width=True)
    else:
        st.info("ℹ️ Nincs még rögzített adat. Adj hozzá kiadásokat és bevételeket a megfelelő menüpontokban!")

if __name__ == "__main__":
    main()
