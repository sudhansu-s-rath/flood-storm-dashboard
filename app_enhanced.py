import streamlit as st
import xarray as xr
import leafmap.foliumap as leafmap
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
import numpy as np

@st.cache_resource
def load_data():
    ds = xr.open_dataset("data/sample.nc", engine="netcdf4")
    return ds

try:
    import localtileserver
    st.write("localtileserver is installed!")
except ImportError:
    st.error("localtileserver is NOT installed!")

st.title("🌧️ Extreme Rainfall Explorer")
st.write("**Click anywhere on the map** to view rainfall time series at that location.")

ds = load_data()

# Calculate spatial mean for map
avg_map = ds['pr'].mean(dim='time')  # Average over time

# Set CRS and spatial dims explicitly
avg_map.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
avg_map.rio.write_crs("EPSG:4326", inplace=True)

# Export to GeoTIFF
avg_map.rio.to_raster("temp.tif")

# Create bounds for the data
bounds = [
    [float(ds.lat.min()), float(ds.lon.min())],
    [float(ds.lat.max()), float(ds.lon.max())]
]

# Create folium map
center_lat = float((ds.lat.min() + ds.lat.max()) / 2)
center_lon = float((ds.lon.min() + ds.lon.max()) / 2)

m = folium.Map(location=[center_lat, center_lon], zoom_start=6)

# Add the raster data using leafmap for better handling
leafmap_obj = leafmap.Map(center=[center_lat, center_lon], zoom=6)
leafmap_obj.add_raster("temp.tif", layer_name="Mean Extreme Precip", opacity=0.7)

# Convert leafmap to folium for better click handling
folium_map = folium.Map(location=[center_lat, center_lon], zoom_start=6)

# Add a custom tile layer or use the generated raster
try:
    # Try to add as image overlay
    folium.raster_layers.ImageOverlay(
        image="temp.tif",
        bounds=bounds,
        opacity=0.7,
        name="Mean Extreme Precip"
    ).add_to(folium_map)
except:
    # If that fails, just show the base map
    pass

# Add layer control
folium.LayerControl().add_to(folium_map)

# Display the map with click functionality
st.subheader("Interactive Map")
map_data = st_folium(folium_map, height=600, width=800)

# Show data bounds
st.info(f"📍 Data coverage: Latitude {ds.lat.min().values:.2f}° to {ds.lat.max().values:.2f}°, "
        f"Longitude {ds.lon.min().values:.2f}° to {ds.lon.max().values:.2f}°")

# Initialize session state for clicked coordinates
if 'clicked_coords' not in st.session_state:
    st.session_state.clicked_coords = None

# Handle map click
if map_data and map_data['last_clicked']:
    clicked_lat = map_data['last_clicked']['lat']
    clicked_lon = map_data['last_clicked']['lng']
    # Check if the click is within data bounds
    if (ds.lat.min() <= clicked_lat <= ds.lat.max() and 
        ds.lon.min() <= clicked_lon <= ds.lon.max()):
        st.session_state.clicked_coords = (clicked_lat, clicked_lon)
    else:
        st.warning(f"⚠️ Clicked location ({clicked_lat:.2f}, {clicked_lon:.2f}) is outside data coverage area!")

# Manual coordinate input as backup
st.subheader("Manual Coordinate Input")
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
    st.success(f"🎯 Generating time series at lat: {lat:.2f}, lon: {lon:.2f}")
    
    try:
        # Select the nearest point
        ts = ds['pr'].sel(lat=lat, lon=lon, method='nearest')
        actual_lat = float(ts.lat.values)
        actual_lon = float(ts.lon.values)
        
        # Convert to dataframe for plotting
        df = ts.to_dataframe().reset_index()

        # Create the time series plot
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df['time'], df['pr'], linewidth=2, color='#1f77b4', marker='o', markersize=4)
        ax.set_title(f"Extreme Rainfall Time Series\nSelected: ({lat:.2f}, {lon:.2f}) → Actual Grid Point: ({actual_lat:.2f}, {actual_lon:.2f})", 
                    fontsize=14, fontweight='bold')
        ax.set_ylabel("Extreme Rainfall (mm)", fontsize=12)
        ax.set_xlabel("Time", fontsize=12)
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig)
        
        # Display statistics
        st.subheader("📊 Statistics")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Maximum", f"{df['pr'].max():.2f} mm", delta=f"{df['pr'].max() - df['pr'].mean():.2f}")
        with col2:
            st.metric("Minimum", f"{df['pr'].min():.2f} mm", delta=f"{df['pr'].min() - df['pr'].mean():.2f}")
        with col3:
            st.metric("Mean", f"{df['pr'].mean():.2f} mm")
        with col4:
            st.metric("Std Dev", f"{df['pr'].std():.2f} mm")
            
        # Show additional analysis
        st.subheader("📈 Additional Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            # Histogram
            fig_hist, ax_hist = plt.subplots(figsize=(8, 5))
            ax_hist.hist(df['pr'], bins=20, alpha=0.7, color='skyblue', edgecolor='black')
            ax_hist.set_title("Distribution of Extreme Rainfall")
            ax_hist.set_xlabel("Rainfall (mm)")
            ax_hist.set_ylabel("Frequency")
            ax_hist.grid(True, alpha=0.3)
            st.pyplot(fig_hist)
            
        with col2:
            # Box plot
            fig_box, ax_box = plt.subplots(figsize=(6, 5))
            ax_box.boxplot(df['pr'], vert=True)
            ax_box.set_title("Box Plot of Extreme Rainfall")
            ax_box.set_ylabel("Rainfall (mm)")
            ax_box.grid(True, alpha=0.3)
            st.pyplot(fig_box)
            
        # Show data table
        with st.expander("📋 View Raw Data"):
            st.dataframe(df.style.format({'pr': '{:.2f}'}))
            
        # Add download button for the data
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Data as CSV",
            data=csv,
            file_name=f"rainfall_data_{lat:.2f}_{lon:.2f}.csv",
            mime="text/csv"
        )
            
    except Exception as e:
        st.error(f"❌ Error generating time series: {str(e)}")

st.info("💡 **Instructions:** Click anywhere on the map above to generate a time series, or use the manual coordinate input below the map.")

# Add clear button
if st.button("🗑️ Clear Selection"):
    st.session_state.clicked_coords = None
    st.rerun()
