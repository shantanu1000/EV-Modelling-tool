import streamlit as st
import numpy as np
import pandas as pd
import altair as alt

# Title and Sidebar Inputs
st.title("EV Modeling for School Buses")
st.sidebar.header('Parameters')

# Bus Configurations
if "bus_configurations" not in st.session_state:
    st.session_state.bus_configurations = []

# Input and manage Bus Configurations
num_buses_input = st.sidebar.number_input("Number of Buses", 1, 500, 1)
bus_capacity_input = st.sidebar.number_input("Bus Capacity (KW)", 50, 500, 155)
if st.sidebar.button("Add Buses"):
    st.session_state.bus_configurations.append((num_buses_input, bus_capacity_input))

# Display Bus Configurations
st.sidebar.write("Bus Configurations:")
for index, (num, capacity) in enumerate(st.session_state.bus_configurations):
    if st.sidebar.button(f"Remove {num} buses of {capacity} KW", key=f"remove_bus_{index}"):
        del st.session_state.bus_configurations[index]

# Charger Capacity and Charging Window
charger_capacity = st.sidebar.slider("Charger Capacity (KW per hour)", 10, 100, 50)
charging_window = st.sidebar.slider("Charging Window (hours)", 1, 24, 8)
charging_rates = [st.sidebar.slider(f"Charging Rate for Hour {i+1} (KW)", 0.1, 1.0, 0.5, 0.01) for i in range(charging_window)]

# Maximum Demand and Operating Days
max_demand = st.number_input("Maximum Demand per Hour (KW)", 100, 10000, 1000)
selected_days = st.sidebar.multiselect("Select Operating Days", ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"], default=["Mo", "Tu", "We", "Th", "Fr"])

# Function to calculate initial charge levels
@st.cache
def get_initial_charge_levels(num_buses, bus_capacities):
    initial_charge_percentages = np.random.uniform(15, 40, num_buses)
    return initial_charge_percentages / 100 * np.array(bus_capacities)

# Function to calculate the charging schedule
@st.cache
def calculate_charging_schedule(bus_capacities, initial_charge_levels, charging_window, charger_capacity, charging_rates, max_demand):
    num_buses = len(bus_capacities)
    charging_schedule = np.zeros((num_buses, charging_window))
    charging_needs = np.array(bus_capacities) - initial_charge_levels
    
    for hour in range(charging_window):
        remaining_demand = max_demand
        sorted_indices = np.argsort(-charging_needs)  # Sort buses by their charging needs

        for idx in sorted_indices:
            if charging_needs[idx] <= 0 or remaining_demand <= 0:
                continue

            available_capacity = min(charger_capacity * charging_rates[hour], remaining_demand)
            charge_this_hour = min(charging_needs[idx], available_capacity)

            # Ensure indices are within the bounds of the charging_schedule array
            if hour < charging_window and idx < num_buses:
                charging_schedule[idx, hour] = charge_this_hour
                charging_needs[idx] -= charge_this_hour
                remaining_demand -= charge_this_hour

    return charging_schedule

def calculate_total_charge_required(bus_capacities, initial_charge_levels):
    return np.sum(bus_capacities - initial_charge_levels)


# Calculate bus capacities and initial charge levels
num_buses = sum(num for num, _ in st.session_state.bus_configurations)
bus_capacities = [capacity * num for num, capacity in st.session_state.bus_configurations]
initial_charge_levels = get_initial_charge_levels(num_buses, bus_capacities)

# Calculate charging schedule
charging_schedule = calculate_charging_schedule(
    bus_capacities=bus_capacities, 
    initial_charge_levels=initial_charge_levels, 
    charging_window=charging_window, 
    charger_capacity=charger_capacity, 
    charging_rates=charging_rates, 
    max_demand=max_demand
)

# Display configured buses
bus_info_str = "### Configured Buses:\n"
for num, capacity in st.session_state.bus_configurations:
    bus_info_str += f"- {num} buses of {capacity} KW\n"
st.write(bus_info_str)

# Calculate total cost
def calculate_total_cost(charging_schedule, charging_rates):
    total_energy_consumed = np.sum(charging_schedule)
    average_rate = np.mean(charging_rates)
    return total_energy_consumed * average_rate

total_charge_required = calculate_total_charge_required(bus_capacities, initial_charge_levels)
charge_delivered = np.sum(charging_schedule)

# Display charge and cost information
st.write(f"Total charge required to charge all buses to full capacity: {total_charge_required:.2f} KW")
st.write(f"Total charge delivered based on the charging schedule: {charge_delivered:.2f} KW")

total_cost = calculate_total_cost(charging_schedule, charging_rates)
weekly_cost = total_cost * len(selected_days)
average_cost_per_kw = total_cost / charge_delivered if charge_delivered > 0 else 0

st.markdown(f"## **Total Charging Cost per Schedule: ${total_cost:.2f}**")
st.markdown(f"## **Weekly Charging Cost (for {len(selected_days)} days): ${weekly_cost:.2f}**")
st.markdown(f"## **Average Cost per kW: ${average_cost_per_kw:.2f}**")

# Function to convert schedule to DataFrame
def schedule_to_df(charging_schedule):
    df = pd.DataFrame(charging_schedule, columns=[f"Hour {i+1}" for i in range(charging_window)])
    df['Bus Index'] = df.index
    return df.melt(id_vars='Bus Index', var_name='Hour', value_name='Charge (KW)')

schedule_df = schedule_to_df(charging_schedule)

# Plot charging schedule
def plot_stacked_area_chart_altair(charging_schedule, charging_window):
    df = pd.DataFrame(charging_schedule).reset_index().melt(id_vars='index')
    df.columns = ['Bus', 'Hour', 'Charge (KW)']
    chart = alt.Chart(df).mark_area().encode(
        x='Hour:O',
        y=alt.Y('sum(Charge (KW)):Q', stack='zero'),
        color='Bus:N',
        tooltip=['Hour', 'Bus', 'sum(Charge (KW))']
    ).properties(width=1000, height=750, title='Charging Distribution for Each Bus Over the Hour Window')
    st.altair_chart(chart)

plot_stacked_area_chart_altair(charging_schedule, charging_window)

def plot_schedule_altair(df):
    chart = alt.Chart(df).mark_rect().encode(
        x='Hour:O',
        y='Bus Index:O',
        color='Charge (KW):Q',
        tooltip=['Bus Index', 'Hour', 'Charge (KW)']
    ).properties(width=1000, height=1000, title='Charging Schedule for Buses')
    st.altair_chart(chart)

plot_schedule_altair(schedule_df)

# Monte Carlo Simulation for Initial Charges
@st.cache
def monte_carlo_initial_charges(bus_configurations, iterations=10000):
    total_charge_required = []
    for _ in range(iterations):
        simulated_initial_charges = [np.random.uniform(15, 40, num) / 100 * capacity for num, capacity in bus_configurations]
        all_initial_charges = [charge for charges in simulated_initial_charges for charge in charges]
        total_additional_charge = sum(capacity - charge for charge, capacity in zip(all_initial_charges, bus_capacities))
        total_charge_required.append(total_additional_charge)
    return total_charge_required

# Plot distribution of Monte Carlo results
def plot_charge_distribution(total_charge_required):
    data = pd.DataFrame({'Total Additional Charge Required (KW)': total_charge_required})
    chart = alt.Chart(data).mark_bar().encode(
        x=alt.X("Total Additional Charge Required (KW)", bin=alt.Bin(maxbins=50)),
        y='count()'
    ).properties(width=600, height=400, title="Distribution of Total Additional Charge Required (10000 Iterations)")
    st.altair_chart(chart)

# Run and plot Monte Carlo Simulation
if st.button("Run Monte Carlo Simulation"):
    total_charge_required = monte_carlo_initial_charges(st.session_state.bus_configurations)
    plot_charge_distribution(total_charge_required)
