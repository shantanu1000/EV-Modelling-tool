import streamlit as st
import numpy as np
import pandas as pd
import altair as alt

# Function definitions
@st.cache
def get_initial_charge_levels(bus_configurations):
    initial_charge_levels = []
    for num, capacity in bus_configurations:
        initial_levels = np.random.uniform(15, 40, num) / 100 * capacity
        initial_charge_levels.extend(initial_levels)
    return np.array(initial_charge_levels)
    
@st.cache
def calculate_charging_schedule(bus_configurations, charger_configurations, charging_window, charging_rates):
    total_buses = sum(num for num, _ in bus_configurations)
    bus_capacities = np.array([capacity for num, capacity in bus_configurations for _ in range(num)])
    charging_schedule = np.zeros((total_buses, charging_window))
    initial_charge_levels = get_initial_charge_levels(bus_configurations)

    for hour in range(charging_window):
        charging_needs = bus_capacities - np.sum(charging_schedule, axis=1)
        sorted_indices = np.argsort(-charging_needs)

        for num_chargers, charger_capacity in charger_configurations:
            chargers_used = 0
            for idx in sorted_indices:
                if chargers_used >= num_chargers or charging_needs[idx] <= 0:
                    break

                charge_this_hour = min(charging_needs[idx], charger_capacity * charging_rates[hour])
                charging_schedule[idx, hour] += charge_this_hour
                chargers_used += 1

    return charging_schedule

def calculate_total_cost(charging_schedule, charging_rates):
    total_energy_consumed = np.sum(charging_schedule)
    average_rate = np.mean(charging_rates)
    return total_energy_consumed * average_rate

def schedule_to_df(charging_schedule):
    df = pd.DataFrame(charging_schedule, columns=[f"Hour {i+1}" for i in range(charging_window)])
    df['Bus Index'] = df.index
    return df.melt(id_vars='Bus Index', var_name='Hour', value_name='Charge (KW)')

def prepare_charger_allocation_data(charging_schedule, num_chargers):
    hours = charging_schedule.shape[1]
    charger_allocation = []

    for hour in range(hours):
        chargers_used = 0
        for bus_index, charge in enumerate(charging_schedule[:, hour]):
            if charge > 0 and chargers_used < num_chargers:
                charger_allocation.append({
                    'Hour': hour + 1,
                    'Charger': chargers_used + 1,
                    'Bus': bus_index + 1,
                    'Charge': charge
                })
                chargers_used += 1

    return pd.DataFrame(charger_allocation)

def plot_stacked_area_chart_altair(charging_schedule, charging_window):
    # Convert the numpy array to a pandas DataFrame
    df = pd.DataFrame(charging_schedule, columns=[f'Hour {i+1}' for i in range(charging_window)])
    df.reset_index(inplace=True)
    df.rename(columns={'index': 'Bus'}, inplace=True)

    # Melt the DataFrame to long format suitable for Altair
    melted_df = df.melt(id_vars=['Bus'], var_name='Hour', value_name='Charge (KW)')

    # Ensure data types are appropriate for plotting
    melted_df['Bus'] = melted_df['Bus'].astype(str)
    melted_df['Hour'] = melted_df['Hour'].astype(str)
    melted_df['Charge (KW)'] = melted_df['Charge (KW)'].astype(float)

    # Create the Altair chart
    chart = alt.Chart(melted_df).mark_area().encode(
        x='Hour:N',
        y=alt.Y('sum(Charge (KW)):Q', stack='zero'),
        color='Bus:N',
        tooltip=['Hour', 'Bus', 'sum(Charge (KW))']
    ).properties(width=1000, height=750, title='Charging Distribution for Each Bus Over the Charging Window')

    # Display the chart
    st.altair_chart(chart)

def plot_schedule_altair(df):
    chart = alt.Chart(df).mark_rect().encode(
        x='Hour:O', y='Bus Index:O', color='Charge (KW):Q', tooltip=['Bus Index', 'Hour', 'Charge (KW)']
    ).properties(width=1000, height=1000, title='Charging Schedule for Buses')
    st.altair_chart(chart)

def plot_charger_allocation_chart(df):
    chart = alt.Chart(df).mark_rect().encode(
        x='Hour:O', y='Charger:O', color='Bus:N', tooltip=['Hour', 'Charger', 'Bus', 'Charge']
    ).properties(width=800, height=400, title='Charger Allocation to Buses Over Time')
    st.altair_chart(chart)

# Title
st.title("EV Modeling for School Buses")

# Sidebar for Bus and Charger Configurations
st.sidebar.header('Bus Parameters')
if "bus_configurations" not in st.session_state:
    st.session_state.bus_configurations = []

num_buses_input = st.sidebar.number_input("Number of Buses", 1, 500, 1)
bus_capacity_input = st.sidebar.number_input("Bus Capacity (KW)", 50, 500, 155)
if st.sidebar.button("Add Buses"):
    st.session_state.bus_configurations.append((num_buses_input, bus_capacity_input))

st.sidebar.write("Bus Configurations:")
for index, (num, capacity) in enumerate(st.session_state.bus_configurations):
    if st.sidebar.button(f"Remove {num} buses of {capacity} KW", key=f"remove_bus_{index}"):
        del st.session_state.bus_configurations[index]

st.sidebar.header('Charger Parameters')
if "charger_configurations" not in st.session_state:
    st.session_state.charger_configurations = []

num_chargers_input = st.sidebar.number_input("Number of Chargers", 1, 500, 1, key="num_chargers")
charger_capacity_input = st.sidebar.number_input("Charger Capacity (KW)", 10, 500, 50, key="charger_capacity")
if st.sidebar.button("Add Charger"):
    st.session_state.charger_configurations.append((num_chargers_input, charger_capacity_input))

st.sidebar.write("Charger Configurations:")
for index, (num, capacity) in enumerate(st.session_state.charger_configurations):
    if st.sidebar.button(f"Remove {num} chargers of {capacity} KW", key=f"remove_charger_{index}"):
        del st.session_state.charger_configurations[index]

# Other inputs
charging_window = st.sidebar.slider("Charging Window (hours)", 1, 24, 8)
charging_rates = [st.sidebar.slider(f"Charging Rate for Hour {i+1} (KW)", 0.1, 1.0, 0.5, 0.01) for i in range(charging_window)]
selected_days = st.sidebar.multiselect("Select Operating Days", ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"], default=["Mo", "Tu", "We", "Th", "Fr"])

# Main Script Logic
num_buses = sum(num for num, _ in st.session_state.bus_configurations)
if num_buses > 0:
    bus_capacities = [capacity * num for num, capacity in st.session_state.bus_configurations]
    initial_charge_levels = get_initial_charge_levels(st.session_state.bus_configurations)
    charger_configurations = st.session_state.charger_configurations
    charging_schedule = calculate_charging_schedule(
        st.session_state.bus_configurations, 
        st.session_state.charger_configurations, 
        charging_window, 
        charging_rates
    )
    total_charge_required = np.sum(bus_capacities) - np.sum(initial_charge_levels)
    charge_delivered = np.sum(charging_schedule)
    st.write(f"Total charge required to charge all buses to full capacity: {total_charge_required:.2f} KW")
    st.write(f"Total charge delivered based on the charging schedule: {charge_delivered:.2f} KW")

    total_cost = calculate_total_cost(charging_schedule, charging_rates)
    weekly_cost = total_cost * len(selected_days)
    average_cost_per_kw = total_cost / charge_delivered
    st.markdown(f"## **Total Charging Cost per Schedule: ${total_cost:.2f}**")
    st.markdown(f"## **Weekly Charging Cost (for {len(selected_days)} days): ${weekly_cost:.2f}**")
    st.markdown(f"## **Average Cost per kW: ${average_cost_per_kw:.2f}**")

    schedule_df = schedule_to_df(charging_schedule)
    plot_stacked_area_chart_altair(charging_schedule, charging_window)
    plot_schedule_altair(schedule_df)

    charger_allocation_df = prepare_charger_allocation_data(charging_schedule, sum(num for num, _ in charger_configurations))
    plot_charger_allocation_chart(charger_allocation_df)
else:
    st.warning("Please add at least one bus configuration.")
