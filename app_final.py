import streamlit as st
import xarray as xr
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
import leafmap.foliumap as leafmap
import rioxarray as rxr

st.set_page_config(page_title="🌧️ Flood Storm Dashboard", layout="wide")

st.title("🌧️ Extreme Rainfall Explorer")
st.markdown("**Click anywhere on the map to view yearly maximum rainfall time series at that location.**")

@st.cache_resource
def load_and_process_data():
    """Load NetCDF data and process it for yearly analysis"""
    try:
        # Load dataset
        ds = xr.open_dataset("data/sample.nc", engine="netcdf4")
        
        # Use xarray's native datetime handling for grouping
        # Group by year and calculate maximum (extreme values)
        yearly_max = ds.groupby(ds['time'].dt.year).max('time')
        
        # Calculate mean across years for mapping
        yearly_mean = yearly_max['pr'].mean(dim='year')
        
        return ds, yearly_max, yearly_mean, None
    except Exception as e:
        return None, None, None, str(e)

# Load data
ds, yearly_ds, yearly_mean, error = load_and_process_data()

if error:
    st.error(f"❌ Error loading data: {error}")
    st.stop()

# Display dataset info
with st.expander("📊 Dataset Information"):
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Original Dataset:**")
        st.write(f"- Shape: {dict(ds.dims)}")
        st.write(f"- Time range: {ds.time.min().values} to {ds.time.max().values}")
    
    with col2:
        st.write("**Yearly Processed Data:**")
        st.write(f"- Shape: {dict(yearly_ds.dims)}")
        st.write(f"- Year range: {yearly_ds.year.min().values} to {yearly_ds.year.max().values}")

# Create map
st.subheader("🗺️ Interactive Map")

# Get map center and bounds
center_lat = float((ds.lat.min() + ds.lat.max()) / 2)
center_lon = float((ds.lon.min() + ds.lon.max()) / 2)

# Create map with precipitation data overlay
st.write("**Creating precipitation overlay...**")

# Debug information
st.write(f"- Data shape: {yearly_mean.shape}")
st.write(f"- Data range: {yearly_mean.min().values:.6f} to {yearly_mean.max().values:.6f}")

# Create folium map
folium_map = folium.Map(location=[center_lat, center_lon], zoom_start=6)

# Method 1: Try leafmap raster overlay
overlay_success = False
try:
    # Ensure we have rio accessor
    if not hasattr(yearly_mean, 'rio'):
        yearly_mean = yearly_mean.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    
    # Set CRS
    yearly_mean = yearly_mean.rio.write_crs("EPSG:4326")
    
    # Save to GeoTIFF
    yearly_mean.rio.to_raster("temp_yearly_mean.tif")
    
    # Create leafmap
    m = leafmap.Map(center=[center_lat, center_lon], zoom=6)
    m.add_raster("temp_yearly_mean.tif", 
                 layer_name="Yearly Max Precipitation", 
                 opacity=0.8, 
                 colormap="viridis")
    
    # Convert to folium
    folium_map = m.to_folium()
    overlay_success = True
    st.success("✅ Leafmap raster overlay created successfully!")
    
except Exception as e:
    st.warning(f"⚠️ Leafmap method failed: {str(e)}")

# Method 2: If leafmap fails, create detailed grid visualization
if not overlay_success:
    st.info("💡 Using enhanced grid visualization instead of raster overlay")
    
    # Add data coverage rectangle
    bounds = [
        [float(ds.lat.min()), float(ds.lon.min())],
        [float(ds.lat.max()), float(ds.lon.max())]
    ]
    
    folium.Rectangle(
        bounds=bounds,
        color='red',
        fill=True,
        fillColor='red',
        fillOpacity=0.1,
        popup='Data Coverage Area'
    ).add_to(folium_map)
    
    # Create high-resolution grid overlay
    lat_points = np.linspace(ds.lat.min(), ds.lat.max(), 30)
    lon_points = np.linspace(ds.lon.min(), ds.lon.max(), 30)
    
    # Get min/max for color scaling
    min_val = yearly_mean.min().values
    max_val = yearly_mean.max().values
    
    # Add colored grid points
    for i, lat in enumerate(lat_points):
        for j, lon in enumerate(lon_points):
            try:
                value = yearly_mean.sel(lat=lat, lon=lon, method='nearest').values
                
                # Normalize for color (0-1)
                normalized = (value - min_val) / (max_val - min_val)
                
                # Create viridis-like color
                if normalized < 0.25:
                    color = f'rgb({int(68*normalized/0.25)}, {int(1*normalized/0.25)}, {int(84*normalized/0.25)})'
                elif normalized < 0.5:
                    color = f'rgb({int(49*(normalized-0.25)/0.25)}, {int(104*(normalized-0.25)/0.25)}, {int(142*(normalized-0.25)/0.25)})'
                elif normalized < 0.75:
                    color = f'rgb({int(53*(normalized-0.5)/0.25)}, {int(183*(normalized-0.5)/0.25)}, {int(121*(normalized-0.5)/0.25)})'
                else:
                    color = f'rgb({int(253*(normalized-0.75)/0.25)}, {int(231*(normalized-0.75)/0.25)}, {int(37*(normalized-0.75)/0.25)})'
                
                folium.CircleMarker(
                    location=[float(lat), float(lon)],
                    radius=2,
                    popup=f'Precipitation: {value:.6f}<br>Lat: {lat:.2f}, Lon: {lon:.2f}',
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=0.8,
                    weight=1
                ).add_to(folium_map)
                
            except Exception as e:
                continue
    
    # Add custom legend
    legend_html = '''
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 200px; height: 150px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:12px; padding: 10px; border-radius: 5px;">
    <h4 style="margin: 0 0 10px 0;">Precipitation</h4>
    <div style="background: linear-gradient(to top, #440154, #31688e, #35b779, #fde725); 
                height: 80px; width: 20px; margin: 5px 0; float: left;"></div>
    <div style="margin-left: 30px; font-size: 10px;">
        <div style="margin-bottom: 50px;">High</div>
        <div>Low</div>
    </div>
    <div style="clear: both; font-size: 10px; margin-top: 5px;">kg m⁻² s⁻¹</div>
    </div>
    '''
    folium_map.get_root().html.add_child(folium.Element(legend_html))
    
    st.success("✅ Enhanced grid visualization created!")

# Add layer control
folium.LayerControl().add_to(folium_map)

# Display the map
map_data = st_folium(folium_map, height=600, width=None)

# Show data coverage info
st.info(f"📍 **Data Coverage:** Latitude {ds.lat.min().values:.2f}° to {ds.lat.max().values:.2f}°, "
        f"Longitude {ds.lon.min().values:.2f}° to {ds.lon.max().values:.2f}°")

# Initialize session state
if 'selected_coords' not in st.session_state:
    st.session_state.selected_coords = None

# Handle map clicks
if map_data and map_data['last_clicked']:
    clicked_lat = map_data['last_clicked']['lat']
    clicked_lon = map_data['last_clicked']['lng']
    
    # Validate click is within data bounds
    if (ds.lat.min() <= clicked_lat <= ds.lat.max() and 
        ds.lon.min() <= clicked_lon <= ds.lon.max()):
        st.session_state.selected_coords = (clicked_lat, clicked_lon)
        st.success(f"🎯 Selected location: {clicked_lat:.2f}, {clicked_lon:.2f}")
    else:
        st.warning(f"⚠️ Location ({clicked_lat:.2f}, {clicked_lon:.2f}) is outside data coverage!")

# Manual coordinate input
st.subheader("🎯 Manual Coordinate Selection")
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    manual_lat = st.number_input(
        "Latitude", 
        value=center_lat, 
        min_value=float(ds.lat.min()), 
        max_value=float(ds.lat.max()),
        format="%.2f"
    )

with col2:
    manual_lon = st.number_input(
        "Longitude", 
        value=center_lon, 
        min_value=float(ds.lon.min()), 
        max_value=float(ds.lon.max()),
        format="%.2f"
    )

with col3:
    st.write("")  # spacer
    if st.button("📍 Select Location", type="primary"):
        st.session_state.selected_coords = (manual_lat, manual_lon)

# Generate time series if coordinates are selected
if st.session_state.selected_coords:
    lat, lon = st.session_state.selected_coords
    
    try:
        # Get time series at selected location
        ts = yearly_ds['pr'].sel(lat=lat, lon=lon, method='nearest')
        actual_lat = float(ts.lat.values)
        actual_lon = float(ts.lon.values)
        
        st.subheader("📈 Time Series Analysis")
        st.info(f"**Selected:** {lat:.2f}, {lon:.2f} → **Nearest Grid Point:** {actual_lat:.2f}, {actual_lon:.2f}")
        
        # Convert to dataframe
        df = ts.to_dataframe().reset_index()
        
        # Create time series plot
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df['year'], df['pr'], 'o-', linewidth=2, markersize=6, color='#1f77b4')
        ax.set_title(f'Yearly Maximum Extreme Precipitation\nLocation: {actual_lat:.2f}°N, {actual_lon:.2f}°E', 
                     fontsize=14, fontweight='bold')
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Precipitation (kg m⁻² s⁻¹)', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Add trend line
        z = np.polyfit(df['year'], df['pr'], 1)
        p = np.poly1d(z)
        ax.plot(df['year'], p(df['year']), '--', alpha=0.8, color='red', linewidth=2, 
                label=f'Trend: {z[0]:.2e} per year')
        ax.legend()
        
        plt.tight_layout()
        st.pyplot(fig)
        
        # Statistics
        st.subheader("📊 Statistics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Maximum", f"{df['pr'].max():.6f}")
        with col2:
            st.metric("Minimum", f"{df['pr'].min():.6f}")
        with col3:
            st.metric("Mean", f"{df['pr'].mean():.6f}")
        with col4:
            st.metric("Trend/Year", f"{z[0]:.2e}")
        
        # Additional analysis
        st.subheader("🔍 Additional Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Distribution histogram
            fig_hist, ax_hist = plt.subplots(figsize=(8, 5))
            ax_hist.hist(df['pr'], bins=15, alpha=0.7, color='skyblue', edgecolor='black')
            ax_hist.set_title('Distribution of Yearly Maximum Precipitation')
            ax_hist.set_xlabel('Precipitation (kg m⁻² s⁻¹)')
            ax_hist.set_ylabel('Frequency')
            ax_hist.grid(True, alpha=0.3)
            st.pyplot(fig_hist)
        
        with col2:
            # Box plot
            fig_box, ax_box = plt.subplots(figsize=(6, 5))
            ax_box.boxplot(df['pr'], vert=True, patch_artist=True, 
                          boxprops=dict(facecolor='lightblue', alpha=0.7))
            ax_box.set_title('Box Plot of Yearly Maximum Precipitation')
            ax_box.set_ylabel('Precipitation (kg m⁻² s⁻¹)')
            ax_box.grid(True, alpha=0.3)
            st.pyplot(fig_box)
        
        # Period comparison
        st.subheader("📅 Period Comparison")
        mid_year = int((df['year'].min() + df['year'].max()) / 2)
        
        col1, col2 = st.columns(2)
        
        with col1:
            early_period = df[df['year'] <= mid_year]
            st.metric(f"Early Period ({df['year'].min()}-{mid_year})", 
                     f"{early_period['pr'].mean():.6f}",
                     delta=f"±{early_period['pr'].std():.6f}")
        
        with col2:
            late_period = df[df['year'] > mid_year]
            st.metric(f"Late Period ({mid_year+1}-{df['year'].max()})", 
                     f"{late_period['pr'].mean():.6f}",
                     delta=f"±{late_period['pr'].std():.6f}")
        
        # Data table
        with st.expander("📋 View Raw Data"):
            st.dataframe(df.style.format({'pr': '{:.8f}'}))
        
        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Data (CSV)",
            data=csv,
            file_name=f"precipitation_data_{actual_lat:.2f}_{actual_lon:.2f}.csv",
            mime="text/csv"
        )
        
    except Exception as e:
        st.error(f"❌ Error generating time series: {str(e)}")
        import traceback
        st.error(traceback.format_exc())

# Clear selection button
if st.session_state.selected_coords:
    if st.button("🗑️ Clear Selection"):
        st.session_state.selected_coords = None
        st.rerun()

# Footer
st.markdown("---")
st.markdown("💡 **Instructions:** Click anywhere on the map or use manual coordinate input to generate yearly maximum precipitation time series.")
