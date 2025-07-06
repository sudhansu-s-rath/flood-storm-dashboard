import streamlit as st
import xarray as xr
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium

st.title("🌧️ Flood Storm Dashboard - Debug Version")

# Load and inspect data
@st.cache_resource
def load_data():
    try:
        ds = xr.open_dataset("data/sample.nc", engine="netcdf4")
        return ds, None
    except Exception as e:
        return None, str(e)

ds, error = load_data()

if error:
    st.error(f"Error loading data: {error}")
    st.stop()

if ds is None:
    st.error("No data loaded")
    st.stop()

# Display dataset information
st.subheader("Dataset Information")
col1, col2 = st.columns(2)

with col1:
    st.write("**Dataset Overview:**")
    st.write(f"- Shape: {dict(ds.dims)}")
    st.write(f"- Data variables: {list(ds.data_vars.keys())}")
    st.write(f"- Coordinates: {list(ds.coords.keys())}")

with col2:
    st.write("**Data Ranges:**")
    if 'pr' in ds.data_vars:
        pr_data = ds['pr']
        st.write(f"- Precipitation: {pr_data.min().values:.6f} to {pr_data.max().values:.6f}")
    if 'time' in ds.coords:
        st.write(f"- Time: {ds.time.min().values} to {ds.time.max().values}")
    if 'lat' in ds.coords:
        st.write(f"- Latitude: {ds.lat.min().values:.2f} to {ds.lat.max().values:.2f}")
    if 'lon' in ds.coords:
        st.write(f"- Longitude: {ds.lon.min().values:.2f} to {ds.lon.max().values:.2f}")

# Process yearly data
@st.cache_resource
def process_yearly_data(ds):
    try:
        # Convert time to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(ds.time):
            ds['time'] = pd.to_datetime(ds.time.values)
        
        # Group by year and calculate maximum
        yearly_max = ds.groupby('time.year').max('time')
        
        # Calculate mean across years for mapping
        yearly_mean = yearly_max['pr'].mean(dim='year')
        
        return yearly_max, yearly_mean, None
    except Exception as e:
        return None, None, str(e)

yearly_ds, yearly_mean, yearly_error = process_yearly_data(ds)

if yearly_error:
    st.error(f"Error processing yearly data: {yearly_error}")
    st.stop()

st.subheader("Yearly Data Processing")
col1, col2 = st.columns(2)

with col1:
    st.write("**Yearly Data:**")
    st.write(f"- Shape: {dict(yearly_ds.dims)}")
    st.write(f"- Years: {yearly_ds.year.min().values} to {yearly_ds.year.max().values}")

with col2:
    st.write("**Yearly Mean for Mapping:**")
    st.write(f"- Shape: {dict(yearly_mean.dims)}")
    st.write(f"- Range: {yearly_mean.min().values:.6f} to {yearly_mean.max().values:.6f}")

# Create map with data overlay
st.subheader("Interactive Map")

# Get map bounds
center_lat = float((ds.lat.min() + ds.lat.max()) / 2)
center_lon = float((ds.lon.min() + ds.lon.max()) / 2)

# Create basic folium map
m = folium.Map(location=[center_lat, center_lon], zoom_start=6)

# Add data bounds rectangle
bounds = [
    [float(ds.lat.min()), float(ds.lon.min())],
    [float(ds.lat.max()), float(ds.lon.max())]
]

folium.Rectangle(
    bounds=bounds,
    color='red',
    fill=True,
    fillColor='blue',
    fillOpacity=0.3,
    popup=f'Data Coverage Area<br>Lat: {ds.lat.min().values:.2f} to {ds.lat.max().values:.2f}<br>Lon: {ds.lon.min().values:.2f} to {ds.lon.max().values:.2f}'
).add_to(m)

# Add grid points as markers (sample some points)
lat_points = np.linspace(ds.lat.min(), ds.lat.max(), 5)
lon_points = np.linspace(ds.lon.min(), ds.lon.max(), 5)

for lat in lat_points:
    for lon in lon_points:
        # Get the mean value at this point
        try:
            value = yearly_mean.sel(lat=lat, lon=lon, method='nearest').values
            folium.CircleMarker(
                location=[float(lat), float(lon)],
                radius=5,
                popup=f'Lat: {lat:.2f}, Lon: {lon:.2f}<br>Mean: {value:.6f}',
                color='green',
                fill=True,
                fillColor='green',
                fillOpacity=0.7
            ).add_to(m)
        except:
            pass

# Display the map
map_data = st_folium(m, height=500, width=800)

# Handle map clicks
st.subheader("Click Analysis")

if map_data and map_data['last_clicked']:
    clicked_lat = map_data['last_clicked']['lat']
    clicked_lon = map_data['last_clicked']['lng']
    
    st.success(f"Clicked at: Lat {clicked_lat:.2f}, Lon {clicked_lon:.2f}")
    
    # Check if click is within bounds
    if (ds.lat.min() <= clicked_lat <= ds.lat.max() and 
        ds.lon.min() <= clicked_lon <= ds.lon.max()):
        
        try:
            # Get yearly time series at clicked location
            ts = yearly_ds['pr'].sel(lat=clicked_lat, lon=clicked_lon, method='nearest')
            actual_lat = float(ts.lat.values)
            actual_lon = float(ts.lon.values)
            
            st.info(f"Nearest grid point: Lat {actual_lat:.2f}, Lon {actual_lon:.2f}")
            
            # Convert to dataframe
            df = ts.to_dataframe().reset_index()
            
            # Plot time series
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(df['year'], df['pr'], 'o-', linewidth=2, markersize=6)
            ax.set_title(f'Yearly Maximum Precipitation Time Series\nLocation: {actual_lat:.2f}, {actual_lon:.2f}')
            ax.set_xlabel('Year')
            ax.set_ylabel('Precipitation (kg m⁻² s⁻¹)')
            ax.grid(True, alpha=0.3)
            st.pyplot(fig)
            
            # Show data table
            st.subheader("Data Table")
            st.dataframe(df)
            
        except Exception as e:
            st.error(f"Error processing click: {str(e)}")
            import traceback
            st.error(traceback.format_exc())
    else:
        st.warning("Click is outside data coverage area")

# Manual coordinate input
st.subheader("Manual Coordinate Input")
col1, col2, col3 = st.columns(3)

with col1:
    manual_lat = st.number_input("Latitude", 
                                value=center_lat, 
                                min_value=float(ds.lat.min()), 
                                max_value=float(ds.lat.max()))
with col2:
    manual_lon = st.number_input("Longitude", 
                                value=center_lon, 
                                min_value=float(ds.lon.min()), 
                                max_value=float(ds.lon.max()))
with col3:
    st.write("")  # spacer
    if st.button("Generate Time Series"):
        try:
            # Get yearly time series at manual location
            ts = yearly_ds['pr'].sel(lat=manual_lat, lon=manual_lon, method='nearest')
            actual_lat = float(ts.lat.values)
            actual_lon = float(ts.lon.values)
            
            st.success(f"Generated time series for: Lat {actual_lat:.2f}, Lon {actual_lon:.2f}")
            
            # Convert to dataframe
            df = ts.to_dataframe().reset_index()
            
            # Plot time series
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(df['year'], df['pr'], 'o-', linewidth=2, markersize=6)
            ax.set_title(f'Yearly Maximum Precipitation Time Series\nLocation: {actual_lat:.2f}, {actual_lon:.2f}')
            ax.set_xlabel('Year')
            ax.set_ylabel('Precipitation (kg m⁻² s⁻¹)')
            ax.grid(True, alpha=0.3)
            st.pyplot(fig)
            
            # Show statistics
            st.subheader("Statistics")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Maximum", f"{df['pr'].max():.6f}")
            with col2:
                st.metric("Minimum", f"{df['pr'].min():.6f}")
            with col3:
                st.metric("Mean", f"{df['pr'].mean():.6f}")
            with col4:
                st.metric("Std Dev", f"{df['pr'].std():.6f}")
            
        except Exception as e:
            st.error(f"Error generating time series: {str(e)}")
            import traceback
            st.error(traceback.format_exc())
