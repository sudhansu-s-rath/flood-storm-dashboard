import streamlit as st
import xarray as xr
import leafmap.foliumap as leafmap
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
import numpy as np
import pandas as pd
from datetime import datetime

@st.cache_resource
def load_data():
    ds = xr.open_dataset("data/sample.nc", engine="netcdf4")
    # Convert time to datetime
    ds['time'] = pd.to_datetime(ds.time.values)
    return ds

@st.cache_resource
def prepare_yearly_data(ds):
    # Calculate yearly maximum values (extreme rainfall)
    yearly_max = ds.groupby('time.year').max('time')
    return yearly_max

try:
    import localtileserver
    st.write("localtileserver is installed!")
except ImportError:
    st.error("localtileserver is NOT installed!")

st.title("🌧️ Extreme Rainfall Explorer")
st.write("**Click anywhere on the map** to view rainfall time series at that location.")

ds = load_data()
yearly_ds = prepare_yearly_data(ds)

# Calculate spatial mean for map using yearly data
avg_map = yearly_ds['pr'].mean(dim='year')  # Average over years

# Set CRS and spatial dims explicitly
avg_map.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
avg_map.rio.write_crs("EPSG:4326", inplace=True)

# Export to GeoTIFF
avg_map.rio.to_raster("temp.tif")

# Create leafmap with the raster overlay
center_lat = float((ds.lat.min() + ds.lat.max()) / 2)
center_lon = float((ds.lon.min() + ds.lon.max()) / 2)

# Use leafmap for proper raster display
m = leafmap.Map(center=[center_lat, center_lon], zoom=6)
m.add_raster("temp.tif", layer_name="Mean Extreme Precip", opacity=0.8, colormap="viridis")

# Convert to folium but keep the raster
folium_map = m.to_folium()

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
    st.success(f"🎯 Generating yearly time series at lat: {lat:.2f}, lon: {lon:.2f}")
    
    try:
        # Select the nearest point from yearly data
        ts_yearly = yearly_ds['pr'].sel(lat=lat, lon=lon, method='nearest')
        actual_lat = float(ts_yearly.lat.values)
        actual_lon = float(ts_yearly.lon.values)
        
        # Convert to dataframe for plotting
        df_yearly = ts_yearly.to_dataframe().reset_index()
        df_yearly.columns = ['year', 'pr']
        
        # Create the yearly time series plot
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df_yearly['year'], df_yearly['pr'], linewidth=2, color='#1f77b4', marker='o', markersize=6)
        ax.set_title(f"Yearly Maximum Extreme Rainfall Time Series\nSelected: ({lat:.2f}, {lon:.2f}) → Actual Grid Point: ({actual_lat:.2f}, {actual_lon:.2f})", 
                    fontsize=14, fontweight='bold')
        ax.set_ylabel("Yearly Maximum Extreme Rainfall (kg m⁻² s⁻¹)", fontsize=12)
        ax.set_xlabel("Year", fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Add trend line
        z = np.polyfit(df_yearly['year'], df_yearly['pr'], 1)
        p = np.poly1d(z)
        ax.plot(df_yearly['year'], p(df_yearly['year']), "r--", alpha=0.8, linewidth=2, label=f'Trend: {z[0]:.2e} per year')
        ax.legend()
        
        plt.tight_layout()
        st.pyplot(fig)
        
        # Display statistics
        st.subheader("📊 Yearly Statistics")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Maximum", f"{df_yearly['pr'].max():.4f}", delta=f"{df_yearly['pr'].max() - df_yearly['pr'].mean():.4f}")
        with col2:
            st.metric("Minimum", f"{df_yearly['pr'].min():.4f}", delta=f"{df_yearly['pr'].min() - df_yearly['pr'].mean():.4f}")
        with col3:
            st.metric("Mean", f"{df_yearly['pr'].mean():.4f}")
        with col4:
            st.metric("Trend/Year", f"{z[0]:.2e}")
            
        # Show additional analysis
        st.subheader("📈 Additional Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            # Histogram
            fig_hist, ax_hist = plt.subplots(figsize=(8, 5))
            ax_hist.hist(df_yearly['pr'], bins=20, alpha=0.7, color='skyblue', edgecolor='black')
            ax_hist.set_title("Distribution of Yearly Maximum Rainfall")
            ax_hist.set_xlabel("Rainfall (kg m⁻² s⁻¹)")
            ax_hist.set_ylabel("Frequency")
            ax_hist.grid(True, alpha=0.3)
            st.pyplot(fig_hist)
            
        with col2:
            # Box plot
            fig_box, ax_box = plt.subplots(figsize=(6, 5))
            ax_box.boxplot(df_yearly['pr'], vert=True)
            ax_box.set_title("Box Plot of Yearly Maximum Rainfall")
            ax_box.set_ylabel("Rainfall (kg m⁻² s⁻¹)")
            ax_box.grid(True, alpha=0.3)
            st.pyplot(fig_box)
            
        # Show periods analysis
        st.subheader("🔍 Period Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            # Early period (2015-2050)
            early_period = df_yearly[df_yearly['year'] <= 2050]
            st.metric("Early Period (2015-2050)", 
                     f"Mean: {early_period['pr'].mean():.4f}",
                     delta=f"±{early_period['pr'].std():.4f}")
            
        with col2:
            # Late period (2051-2100)
            late_period = df_yearly[df_yearly['year'] > 2050]
            st.metric("Late Period (2051-2100)", 
                     f"Mean: {late_period['pr'].mean():.4f}",
                     delta=f"±{late_period['pr'].std():.4f}")
            
        # Show data table
        with st.expander("📋 View Yearly Data"):
            st.dataframe(df_yearly.style.format({'pr': '{:.6f}'}))
            
        # Add download button for the yearly data
        csv = df_yearly.to_csv(index=False)
        st.download_button(
            label="📥 Download Yearly Data as CSV",
            data=csv,
            file_name=f"yearly_rainfall_data_{lat:.2f}_{lon:.2f}.csv",
            mime="text/csv"
        )
            
    except Exception as e:
        st.error(f"❌ Error generating time series: {str(e)}")
        import traceback
        st.error(traceback.format_exc())

st.info("💡 **Instructions:** Click anywhere on the map above to generate a yearly time series, or use the manual coordinate input below the map. The analysis shows yearly maximum extreme rainfall values from 2015-2100.")

# Add clear button
if st.button("🗑️ Clear Selection"):
    st.session_state.clicked_coords = None
    st.rerun()
