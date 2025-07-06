import streamlit as st
import xarray as xr
import leafmap.foliumap as leafmap
import matplotlib.pyplot as plt

@st.cache_resource
def load_data():
    ds = xr.open_dataset("data/sample.nc", engine="netcdf4")
    return ds

try:
    import localtileserver
    st.write("localtileserver is installed!")
except ImportError:
    st.error("localtileserver is NOT installed!")

st.title("Extreme Rainfall Explorer")
st.write("Use the manual input below to select coordinates and view rainfall time series.")

ds = load_data()

# Calculate spatial mean for map
avg_map = ds['pr'].mean(dim='time')  # Average over time

# Set CRS and spatial dims explicitly
avg_map.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
avg_map.rio.write_crs("EPSG:4326", inplace=True)

# Export to GeoTIFF
avg_map.rio.to_raster("temp.tif")

# Create map
center_lat = float((ds.lat.min() + ds.lat.max()) / 2)
center_lon = float((ds.lon.min() + ds.lon.max()) / 2)

m = leafmap.Map(center=[center_lat, center_lon], zoom=5)
m.add_raster("temp.tif", layer_name="Mean Extreme Precip")

# Display the map
st.subheader("Rainfall Data Visualization")
m.to_streamlit(height=600)

# Show data bounds
st.info(f"Data coverage: Latitude {ds.lat.min().values:.2f}° to {ds.lat.max().values:.2f}°, "
        f"Longitude {ds.lon.min().values:.2f}° to {ds.lon.max().values:.2f}°")

# Initialize session state for clicked coordinates
if 'clicked_coords' not in st.session_state:
    st.session_state.clicked_coords = None

# Manual coordinate input as backup
st.subheader("Manual Coordinate Input")
col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    lat_min, lat_max = float(ds.lat.min()), float(ds.lat.max())
    lat_default = (lat_min + lat_max) / 2
    manual_lat = st.number_input("Latitude", value=lat_default, min_value=lat_min, max_value=lat_max, key="manual_lat")
with col2:
    lon_min, lon_max = float(ds.lon.min()), float(ds.lon.max())
    lon_default = (lon_min + lon_max) / 2
    manual_lon = st.number_input("Longitude", value=lon_default, min_value=lon_min, max_value=lon_max, key="manual_lon")
with col3:
    st.write("")  # Empty space for alignment
    st.write("")  # Empty space for alignment
    if st.button("Get Time Series", key="manual_button"):
        st.session_state.clicked_coords = (manual_lat, manual_lon)

# Coordinate input for time series generation
st.subheader("Select Coordinates for Time Series")
col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    lat_min, lat_max = float(ds.lat.min()), float(ds.lat.max())
    lat_default = (lat_min + lat_max) / 2
    selected_lat = st.number_input("Latitude", value=lat_default, min_value=lat_min, max_value=lat_max, key="lat_input")
with col2:
    lon_min, lon_max = float(ds.lon.min()), float(ds.lon.max())
    lon_default = (lon_min + lon_max) / 2
    selected_lon = st.number_input("Longitude", value=lon_default, min_value=lon_min, max_value=lon_max, key="lon_input")
with col3:
    st.write("")  # Empty space for alignment
    st.write("")  # Empty space for alignment
    if st.button("Generate Time Series", key="generate_ts"):
        st.session_state.clicked_coords = (selected_lat, selected_lon)

# Check if coordinates are available and generate time series
if st.session_state.clicked_coords:
    lat, lon = st.session_state.clicked_coords
    st.success(f"Generating time series at lat: {lat:.2f}, lon: {lon:.2f}")
    
    try:
        # Select the nearest point
        ts = ds['pr'].sel(lat=lat, lon=lon, method='nearest')
        actual_lat = float(ts.lat.values)
        actual_lon = float(ts.lon.values)
        
        # Convert to dataframe for plotting
        df = ts.to_dataframe().reset_index()

        # Create the time series plot
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df['time'], df['pr'], linewidth=2, color='blue')
        ax.set_title(f"Extreme Rainfall Time Series\nSelected: ({lat:.2f}, {lon:.2f}) → Actual: ({actual_lat:.2f}, {actual_lon:.2f})")
        ax.set_ylabel("Extreme Rainfall (mm)")
        ax.set_xlabel("Time")
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig)
        
        # Display statistics
        st.subheader("Statistics")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Maximum", f"{df['pr'].max():.2f} mm")
        with col2:
            st.metric("Minimum", f"{df['pr'].min():.2f} mm")
        with col3:
            st.metric("Mean", f"{df['pr'].mean():.2f} mm")
        with col4:
            st.metric("Std Dev", f"{df['pr'].std():.2f} mm")
            
        # Show data table
        with st.expander("View Raw Data"):
            st.dataframe(df)
            
    except Exception as e:
        st.error(f"Error generating time series: {str(e)}")

st.info("💡 Click on the map to generate a time series at that location, or use the manual input above.")
