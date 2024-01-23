import streamlit as st
import numpy as np
import pandas as pd
import altair as alt

st.title("EV Modeling for School Buses")

# Sidebar user input for buses
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

bus_capacities = [capacity * num for num, capacity in st.session_state.bus_configurations]

# Sidebar user input for chargers
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

charger_configurations = st.session_state.charger_configurations

# Other inputs
charging_window = st.sidebar.slider("Charging Window (hours)", 1, 24, 8)
charging_rates = [st.sidebar.slider(f"Charging Rate for Hour {i+1} (KW)", 0.1, 1.0, 0.5, 0.01) for i in range(charging_window)]
selected_days = st.sidebar.multiselect("Select Operating Days", ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"], default=["Mo", "Tu", "We", "Th", "Fr"])

# Function definitions
@st.cache
def get_initial_charge_levels(num_buses, bus_capacities):
    initial_charge_percentages = np.random.uniform(15, 40, num_buses)
    return initial_charge_percentages / 100 * np.array(bus_capacities)

@st.cache
def calculate_charging_schedule(bus_capacities, initial_charge_levels, charging_window, charger_configurations, charging_rates):
    charging_needs = np.array(bus_capacities) - initial_charge_levels
    charging_schedule = np.zeros((len(bus_capacities), charging_window))

    for hour in range(charging_window):
        sorted_indices = np.argsort(-charging_needs)

        for num_chargers, charger_capacity in charger_configurations:
            chargers_allocated = 0

            for idx in sorted_indices:
                if chargers_allocated >= num_chargers or charging_needs[idx] <= 0:
                    continue

                charge_this_hour = min(charging_needs[idx], charger_capacity * charging_rates[hour])
                charging_schedule[idx, hour] += charge_this_hour
                charging_needs[idx] -= charge_this_hour
                chargers_allocated += 1

    return charging_schedule

# Main script logic
num_buses = sum(num for num, _ in st.session_state.bus_configurations)

if num_buses > 0:
    initial_charge_levels = get_initial_charge_levels(num_buses, bus_capacities)
    charging_schedule = calculate_charging_schedule(bus_capacities, initial_charge_levels, charging_window, charger_configurations, charging_rates)

    total_charge_required = np.sum(bus_capacities) - np.sum(initial_charge_levels)
    charge_delivered = np.sum(charging_schedule)

    st.write(f"Total charge required to charge all buses to full capacity: {total_charge_required:.2f} KW")
    st.write(f"Total charge delivered based on the charging schedule: {charge_delivered:.2f} KW")

    num_selected_days = len(selected_days)
    total_cost = calculate_total_cost(charging_schedule, charging_rates)
    weekly_cost = total_cost * num_selected_days
    average_cost_per_kw = total_cost / charge_delivered

    st.markdown(f"## **Total Charging Cost per Schedule: ${total_cost:.2f}**")
    st.markdown(f"## **Weekly Charging Cost (for {num_selected_days} days): ${weekly_cost:.2f}**")
    st.markdown(f"## **Average Cost per kW: ${average_cost_per_kw:.2f}**")

    schedule_df = schedule_to_df(charging_schedule)
    plot_stacked_area_chart_altair(charging_schedule, charging_window)
    plot_schedule_altair(schedule_df)

    charger_allocation_df = prepare_charger_allocation_data(charging_schedule, num_chargers)
    plot_charger_allocation_chart(charger_allocation_df)

else:
    st.warning("Please add at least one bus configuration.")

# Supporting function definitions
def calculate_total_cost(charging_schedule, charging_rates):
    total_energy_consumed = np.sum(charging_schedule)
    average_rate = np.mean(charging_rates)
    return total_energy_consumed * average_rate

def schedule_to_df(charging_schedule):
    df = pd.DataFrame(charging_schedule, columns=[f"Hour {i+1}" for i in range(charging_window)])
    df['Bus Index'] = df.index
    return df.melt(id_vars='Bus Index', var_name='Hour', value_name='Charge (KW)')

def plot_stacked_area_chart_altair(charging_schedule, charging_window):
    df = pd.DataFrame(charging_schedule).reset_index().melt(id_vars='index')
    chart = alt.Chart(df).mark_area().encode(
        x='Hour:O', y=alt.Y('sum(Charge (KW)):Q', stack='zero'), color='Bus:N', tooltip=['Hour', 'Bus', 'sum(Charge (KW))']
    ).properties(width=1000, height=750, title='Charging Distribution for Each Bus Over the Hour Window')
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
