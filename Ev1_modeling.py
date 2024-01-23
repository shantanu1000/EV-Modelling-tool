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
to_remove_bus = None
for index, (num, capacity) in enumerate(st.session_state.bus_configurations):
    if st.sidebar.button(f"Remove {num} buses of {capacity} KW", key=f"remove_bus_{index}"):
        to_remove_bus = index
if to_remove_bus is not None:
    del st.session_state.bus_configurations[to_remove_bus]

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
to_remove_charger = None
for index, (num, capacity) in enumerate(st.session_state.charger_configurations):
    if st.sidebar.button(f"Remove {num} chargers of {capacity} KW", key=f"remove_charger_{index}"):
        to_remove_charger = index
if to_remove_charger is not None:
    del st.session_state.charger_configurations[to_remove_charger]

charger_configurations = st.session_state.charger_configurations

# Other inputs
charging_window = st.sidebar.slider("Charging Window (hours)", 1, 24, 8)
charging_rates = [st.sidebar.slider(f"Charging Rate for Hour {i+1} (KW)", 0.1, 1.0, 0.5, 0.01) for i in range(charging_window)]
selected_days = st.sidebar.multiselect("Select Operating Days", options=["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"], default=["Mo", "Tu", "We", "Th", "Fr"])

# Function definitions
@st.cache
def get_initial_charge_levels(num_buses, bus_capacities):
    initial_charge_percentages = np.random.uniform(15, 40, num_buses)
    initial_charge_levels = initial_charge_percentages / 100 * np.array(bus_capacities)
    return initial_charge_levels

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


# Set random seed for reproducibility
np.random.seed()


bus_capacities = [capacity * num for num, capacity in st.session_state.bus_configurations]

# Calculate the total number of buses
num_buses = sum(num for num, _ in st.session_state.bus_configurations)

# Ensure that there is at least one bus before proceeding
if num_buses > 0:
    # Prepare the list of charger configurations
    charger_configurations = [(num, capacity) for num, capacity in st.session_state.charger_configurations]

    # Calculate initial charge levels
    initial_charge_levels = get_initial_charge_levels(num_buses, bus_capacities)

    # Call the function with the updated arguments
    charging_schedule = calculate_charging_schedule(
        bus_capacities, 
        initial_charge_levels, 
        charging_window, 
        charger_configurations,  # Use the prepared list of charger configurations
        charging_rates
    )


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

total_charging_time_required = np.sum(charging_schedule) / num_chargers
if total_charging_time_required > charging_window * charger_capacity:
    st.warning("Charging window insufficient, consider extending the charging time or adding more chargers.")


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

print(charger_allocation_df.dtypes)

def plot_charger_allocation_chart(df):
    chart = alt.Chart(df).mark_rect().encode(
        x='Hour:O',  # Ordinal encoding for Hour
        y='Charger:O',  # Ordinal encoding for Charger
        color='Bus:N',  # Nominal encoding for Bus
        tooltip=['Hour', 'Charger', 'Bus', 'Charge']
    ).properties(
        width=800,
        height=400,
        title='Charger Allocation to Buses Over Time'
    )
    st.altair_chart(chart)


# Plot chart
plot_charger_allocation_chart(charger_allocation_df)



