import streamlit as st
import xarray as xr
import leafmap.foliumap as leafmap
import matplotlib.pyplot as plt

@st.cache_resource
def load_data():
    ds = xr.open_dataset("data/sample.nc", engine="netcdf4")
    return ds

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
m.add_click_marker()
m.to_streamlit(height=600)

clicked = m.user_click()

if clicked:
    lon, lat = clicked['lon'], clicked['lat']
    st.success(f"You clicked at lat: {lat:.2f}, lon: {lon:.2f}")
    ts = ds['precip'].sel(lat=lat, lon=lon, method='nearest')
    df = ts.to_dataframe().reset_index()

    fig, ax = plt.subplots()
    ax.plot(df['time'], df['precip'])
    ax.set_title(f"Time Series at ({lat:.2f}, {lon:.2f})")
    ax.set_ylabel("Extreme Rainfall (mm)")
    st.pyplot(fig)
