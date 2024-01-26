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

num_buses_input = st.sidebar.number_input("Number of Buses", 1, 500, 1)
bus_capacity_input = st.sidebar.number_input("Bus Capacity (KW)", 50, 500, 155)
if st.sidebar.button("Add Buses"):
    st.session_state.bus_configurations.append((num_buses_input, bus_capacity_input))

# Display and manage Bus Configurations
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

# Calculate Initial Charge Levels
@st.cache
def get_initial_charge_levels(num_buses, bus_capacities):
    initial_charge_percentages = np.random.uniform(15, 40, num_buses)
    return initial_charge_percentages / 100 * np.array(bus_capacities)

# Calculate Charging Schedule
@st.cache
def calculate_charging_schedule(bus_capacities, initial_charge_levels, charging_window, charger_capacity, charging_rates, max_demand):
    charging_needs = np.array(bus_capacities) - initial_charge_levels
    charging_schedule = np.zeros((len(bus_capacities), charging_window))
    
    for hour in range(charging_window):
        remaining_demand = max_demand
        for idx in np.argsort(-charging_needs):
            if charging_needs[idx] <= 0 or remaining_demand <= 0:
                continue
            charge_this_hour = min(charging_needs[idx], charger_capacity * charging_rates[hour], remaining_demand)
            charging_schedule[idx, hour] = charge_this_hour
            charging_needs[idx] -= charge_this_hour
            remaining_demand -= charge_this_hour
    
    return charging_schedule

# Main Script
num_buses = sum(num for num, _ in st.session_state.bus_configurations)
bus_capacities = [capacity * num for num, capacity in st.session_state.bus_configurations]

if num_buses > 0:
    initial_charge_levels = get_initial_charge_levels(num_buses, bus_capacities)
    charging_schedule = calculate_charging_schedule(bus_capacities, initial_charge_levels, charging_window, charger_capacity, charging_rates, max_demand)




# Set random seed for reproducibility
np.random.seed()


# Get initial charge levels
initial_charge_levels = get_initial_charge_levels(num_buses, bus_capacities)

# Calculate charging schedule
charging_schedule = calculate_charging_schedule(bus_capacities, initial_charge_levels, charging_window, charger_capacity, charging_rates)


bus_info_str = "### Configured Buses:\n"
for num, capacity in st.session_state.bus_configurations:
        bus_info_str += f"- {num} buses of {capacity} KW\n"
st.write(bus_info_str)


def calculate_total_cost(charging_schedule, charging_rates):
    """
    Calculate the total cost based on the charging schedule and average charging rate.
    """
    total_energy_consumed = np.sum(charging_schedule)  # sum all the KW across all buses and hours
    average_rate = np.mean(charging_rates)  # compute the average rate
    total_cost = total_energy_consumed * average_rate
    return total_cost
    


total_charge_required = np.sum(bus_capacities) - np.sum(initial_charge_levels)

# Calculate charge delivered based on the charging schedule
charge_delivered = np.sum(charging_schedule)

st.write(f"Total charge required to charge all buses to full capacity: {total_charge_required:.2f} KW")
st.write(f"Total charge delivered based on the charging schedule: {charge_delivered:.2f} KW")
# Calculate the number of selected days
num_selected_days = len(selected_days)
total_cost = calculate_total_cost(charging_schedule, charging_rates)
# Calculate the weekly cost based on the number of selected days
weekly_cost = total_cost * num_selected_days

# Calculate the average cost per kW
average_cost_per_kw = total_cost / charge_delivered

# Display the total cost in a bold format
st.markdown(f"## **Total Charging Cost per Schedule: ${total_cost:.2f}**")

st.markdown(f"## **Weekly Charging Cost (for {num_selected_days} days): ${weekly_cost:.2f}**")
# Display the average cost per kW in a similar format
st.markdown(f"## **Average Cost per kW: ${average_cost_per_kw:.2f}**")


def schedule_to_df(charging_schedule):
    hours = charging_schedule.shape[1]
    df = pd.DataFrame(charging_schedule, columns=[f"Hour {i+1}" for i in range(hours)])
    df['Bus Index'] = df.index
    return df.melt(id_vars='Bus Index', var_name='Hour', value_name='Charge (KW)')

schedule_df = schedule_to_df(charging_schedule)


def plot_stacked_area_chart_altair(charging_schedule, charging_window):
    df = pd.DataFrame(charging_schedule).reset_index().melt(id_vars='index')
    df.columns = ['Bus', 'Hour', 'Charge (KW)']

    chart = alt.Chart(df).mark_area().encode(
        x='Hour:O',
        y=alt.Y('sum(Charge (KW)):Q', stack='zero'),
        color=alt.Color('Bus:N', scale=alt.Scale(scheme='blues'), legend=None),
        tooltip=['Hour', 'Bus', 'sum(Charge (KW))']
    ).properties(width=1000, height=750, title='Charging Distribution for Each Bus Over the Hour Window')

    st.altair_chart(chart)

# Call the function to plot the chart on Streamlit
plot_stacked_area_chart_altair(charging_schedule, charging_window)

def plot_schedule_altair(df):
    chart = alt.Chart(df).mark_rect().encode(
        x='Hour:O',
        y=alt.Y('Bus Index:O', sort='ascending'),
        color=alt.Color('Charge (KW):Q', scale=alt.Scale(scheme='blues')),
        tooltip=['Bus Index', 'Hour', 'Charge (KW)']
    ).properties(width=1000, height=1000, title='Charging Schedule for Buses')
    st.altair_chart(chart)

plot_schedule_altair(schedule_df)

@st.cache
def monte_carlo_initial_charges(bus_configurations, iterations=10000):
    total_charge_required = []
    for _ in range(iterations):
        # Generate random initial charge levels for each bus configuration
        simulated_initial_charges = [np.random.uniform(15, 40, num) / 100 * capacity for num, capacity in bus_configurations]
        # Flatten the list of lists to a single list of all initial charges
        all_initial_charges = [charge for charges in simulated_initial_charges for charge in charges]
        total_additional_charge = sum(capacity - charge for charge, capacity in zip(all_initial_charges, bus_capacities))
        total_charge_required.append(total_additional_charge)
    return total_charge_required

# Plot Distribution function
def plot_charge_distribution(total_charge_required):
    data = pd.DataFrame({'Total Additional Charge Required (KW)': total_charge_required})
    chart = alt.Chart(data).mark_bar().encode(
        x=alt.X("Total Additional Charge Required (KW)", bin=alt.Bin(maxbins=50)),
        y='count()'
    ).properties(
        width=600,
        height=400,
        title="Distribution of Total Additional Charge Required (10000 Iterations)"
    )
    st.altair_chart(chart)

# Perform Monte Carlo Simulation and Plot
if st.button("Run Monte Carlo Simulation"):
    total_charge_required = monte_carlo_initial_charges(st.session_state.bus_configurations)
    plot_charge_distribution(total_charge_required)
