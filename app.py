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
st.write("Click a point on the map to view rainfall time series at that location.")

ds = load_data()

# Calculate spatial mean for map
avg_map = ds['pr'].mean(dim='time')  # Average over time

# Set CRS and spatial dims explicitly
avg_map.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
avg_map.rio.write_crs("EPSG:4326", inplace=True)

# Export to GeoTIFF
avg_map.rio.to_raster("temp.tif")


m = leafmap.Map(center=[20.5, 85.5], zoom=5)
m.add_raster("temp.tif", layer_name="Mean Extreme Precip")
m.to_streamlit(height=600)

# Use Streamlit's input widgets for lat/lon instead of map clicks
col1, col2 = st.columns(2)
with col1:
    lat = st.number_input("Latitude", value=20.5, min_value=float(ds.lat.min()), max_value=float(ds.lat.max()))
with col2:
    lon = st.number_input("Longitude", value=85.5, min_value=float(ds.lon.min()), max_value=float(ds.lon.max()))

if st.button("Get Time Series"):
    st.success(f"Getting time series at lat: {lat:.2f}, lon: {lon:.2f}")
    ts = ds['pr'].sel(lat=lat, lon=lon, method='nearest')
    df = ts.to_dataframe().reset_index()

    fig, ax = plt.subplots()
    ax.plot(df['time'], df['pr'])
    ax.set_title(f"Time Series at ({lat:.2f}, {lon:.2f})")
    ax.set_ylabel("Extreme Rainfall (mm)")
    st.pyplot(fig)
