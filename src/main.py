import json, requests, pandas as pd
import re
from datetime import date, datetime
import matplotlib.pyplot as plt
import numpy as np
from dataclasses import dataclass, asdict
from typing import Any
from requests.exceptions import HTTPError
import scipy
from PIL import Image
from io import BytesIO

@dataclass
class NasaParams:
    SERVICE: str
    VERSION: str
    REQUEST: str
    LAYERS: str
    STYLES: str
    SRS: str
    BBOX: str
    WIDTH: int
    HEIGHT: int
    FORMAT: str
    TRANSPARENT: str
    TIME: date

@dataclass
class WeatherParams:
    latitude: float
    longitude: float
    start_date: date
    end_date: date
    daily: str
    timezone: str

@dataclass
class City:
    name: str
    latitude: float
    longitude: float

def to_json_nasa(params: NasaParams) -> dict[str, Any]:
    data = asdict(params)
    data["TIME"] = params.TIME.isoformat()
    return data

def to_json(params: WeatherParams) -> dict[str, Any]:
    data = asdict(params)
    data["start_date"] = params.start_date.isoformat()
    data["end_date"] = params.end_date.isoformat()
    return data

default_start_date = date(2025, 1, 1)
default_end_date = date(2025, 12, 31)
default_daily_parameters = ",".join(["temperature_2m_max", "temperature_2m_min", "precipitation_sum"])
default_timezone = "auto"

params_iasi = WeatherParams(
        latitude=47.1667,
        longitude=27.6,
        start_date=default_start_date,
        end_date=default_end_date,
        daily=default_daily_parameters,
        timezone=default_timezone,
        )

URL_weather = "https://archive-api.open-meteo.com/v1/archive"
URL_cities = "https://countries.dev/cities"
URL_nasa = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
params = {
        "latitude": 47.1667, "longitude": 27.6,
        "start_date": "2025-01-01", "end_date": "2025-12-31",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        }

cities = ["Beijing", "Odesa", "Berlin", "Cape Town", "Santiago", "Forth Worth", "Halifax", "New York", "Cairo", "Sanaa", "Singapore", "Iasi", "Bucuresti", "Leipzig", "Accra", "Addis Ababa"]
print(cities)

def make_params_nasa_sgl(city:City):
    delta = 0.45
    latitude = city.latitude
    longitude = city.longitude
    bbox = (
            longitude - delta,
            latitude - delta,
            longitude + delta,
            latitude + delta)
    return NasaParams(
            SERVICE = "WMS",
            VERSION = "1.1.1",
            REQUEST= "GetMap",
            LAYERS= "VIIRS_Black_Marble",
            STYLES= "",
            SRS= "EPSG:4326",
            BBOX= ",".join(map(str, bbox)),
            WIDTH= 800,
            HEIGHT= 800,
            FORMAT= "image/png",
            TRANSPARENT= "FALSE",
            TIME=date(2016, 1, 1),
            )

def make_params(cities:list[str], URL_cities:str)-> list[WeatherParams]:
    city_params = []
    city_coordinates = []
    for city in cities:
        try:
            resp = requests.get(URL_cities, params={"q":city}).json()[0]
            print(resp)
            city_params.append(
                    WeatherParams(
                            latitude=resp["latitude"],
                            longitude=resp["longitude"],
                            start_date=default_start_date,
                            end_date=default_end_date,
                            daily=default_daily_parameters,
                            timezone=default_timezone,
                        )
                    )
            city_coordinates.append(
                    City(
                        name=city,
                        latitude=resp["latitude"],
                        longitude=resp["longitude"]
                        )
                    )
        except requests.exceptions.Timeout:
            print("The API request timed out.")
        except requests.exceptions.ConnectionError:
            print("Could not connect to the API.")
        except requests.exceptions.HTTPError as error:
            print(f"The API returned an HTTP error: {error}")
        except requests.exceptions.JSONDecodeError:
            print("The API response was not valid JSON.")
        except requests.exceptions.RequestException as error:
            print(f"An unexpected request error occurred: {error}")
    return city_params, city_coordinates

def get_weather_for_cities(city_params:list[WeatherParams], URL_weather: str)->list:
    weather_json = []
    for city in city_params:
        try:
            res = requests.get(URL_weather, params=to_json(city))
            weather_json.append(res.json())
        except requests.exceptions.Timeout:
            print("The API request timed out.")
        except requests.exceptions.ConnectionError:
            print("Could not connect to the API.")
        except requests.exceptions.HTTPError as error:
            print(f"The API returned an HTTP error: {error}")
        except requests.exceptions.JSONDecodeError:
            print("The API response was not valid JSON.")
        except requests.exceptions.RequestException as error:
            print(f"An unexpected request error occurred: {error}")
    return weather_json

def descarca(URL :str, params:WeatherParams):
    try:
        res = requests.get(URL, params=to_json(params)).json()
        print(list(res.keys())) 
        return res
    except requests.exceptions.HTTPError as errh:
        print("HTTP error")
        print(errh.args[0])
 
def tdf(res_data, city:City) -> pd.DataFrame:
    api_data = pd.DataFrame(res_data)
    dtime = pd.DatetimeIndex(api_data.loc["time"]["daily"])
    new_df = pd.DataFrame({"temperature_2m_max":api_data.loc['temperature_2m_max']['daily'],
                           "temperature_2m_min":api_data.loc['temperature_2m_min']['daily'],
                           "precipitation_sum":api_data.loc['precipitation_sum']['daily']},                          
                          index=dtime)
    new_df["avg_daily_temp"] = (new_df["temperature_2m_max"] + new_df["temperature_2m_min"])/2
    new_df.index.name = city.name 
    new_df.attrs["city"] = city.name
    new_df.attrs["latitude"] = city.latitude
    new_df.attrs["longitude"] = city.longitude
    
    return new_df 

def plot_wthr_data(df: pd.DataFrame) -> None:
    print(df)
    dtime = pd.DatetimeIndex(df.loc["time"]["daily"])
    print(df.stack().drop_duplicates().drop(["time"]))
    new_df = pd.DataFrame({"temperature_2m_max":df.loc['temperature_2m_max']['daily'],
                           "temperature_2m_min":df.loc['temperature_2m_min']['daily'],
                           "precipitation_sum":df.loc['precipitation_sum']['daily']},                          
                          index=dtime)
    new_df["avg_daily_temp"] = (new_df["temperature_2m_max"] + new_df["temperature_2m_min"])/2
    print(new_df)
    fig, axs = plt.subplots(4,1, sharex=True)
    for ax, cols in zip(axs, new_df.columns):
        ax.plot(new_df.index, new_df[cols])
        ax.grid(True)
    plt.show()

#plot_wthr_data(tdf(descarca(URL, params_iasi)))
def plot_whtr_data_list(dfl:list[pd.DataFrame]) -> None:
    n = len(dfl)

    total_plots = sum(len(df.columns) for df in dfl)

    fig, axs = plt.subplots(
            total_plots,
            n-1,
            figsize=(17, 3 * total_plots),
            sharex=False,
            squeeze=False
            )
    axs = axs.ravel()
    plot_number = 0

    for df_index, df in enumerate(dfl):
        for column in df.columns:
            ax = axs[plot_number]
            ax.plot(df.index, df[column])
            ax.set_xlabel(df.index.name or "Index")
            ax.set_ylabel(column)
            ax.grid(True)
            plot_number+=1
    plt.tight_layout()
    plt.show()
  
def amplitude_latitude_relationship2(dfl:list[pd.DataFrame], weatherParamsList: list[WeatherParams]) -> None:
    x, y = [], []
    diff = [[max(df["avg_daily_temp"])-min(df["avg_daily_temp"]),wp.latitude] for df, wp in zip(dfl, weatherParamsList)]
    for el in diff:
        x.append(el[0])
        y.append(el[1])
    print(x)
    print(y)
    print(diff)
    mat = list(zip(x,y))
    mat.sort(key=lambda pair: pair[1])
    x, y = zip(*mat)
    x = list(x)
    y = np.array(y)
    print(x, y)
    lin = scipy.stats.linregress(y, x)
    xlin = np.arange(len(x))
    ylin = y * lin.slope + lin.intercept
    fig, ax = plt.subplots()
    ax.scatter(y, x)
    ax.plot(y, ylin)
    ax.set_ylabel("latitude")
    ax.set_xlabel("temperature amplitude")
    plt.show()



def amplitude_latitude_relationship(
    dfl: list[pd.DataFrame],
) -> None:
    amplitudes = []
    latitudes = []
    cities = []

    for df in dfl:
        amplitude = (
            df["avg_daily_temp"].max()
            - df["avg_daily_temp"].min()
        )

        amplitudes.append(amplitude)
        latitudes.append(df.attrs["latitude"])
        cities.append(df.attrs["city"])
    data = sorted(
        zip(latitudes, amplitudes, cities),
        key=lambda item: item[0],
    )

    latitudes, amplitudes, cities = zip(*data)

    x = np.array(latitudes)
    y = np.array(amplitudes)
    lin = scipy.stats.linregress(x, y)

    xlin = np.linspace(x.min(), x.max(), 100)
    ylin = lin.slope * xlin + lin.intercept

    fig, ax = plt.subplots(figsize=(10, 6))
    for latitude, amplitude, city in zip(x, y, cities):
        ax.scatter(
            latitude,
            amplitude,
            label=city,
            zorder=3,
        )
        ax.annotate(
            city,
            xy=(latitude, amplitude),
            xytext=(8, 8),
            textcoords="offset points",
            arrowprops={
                "arrowstyle": "->",
                "connectionstyle": "arc3,rad=0.15",
            },
        )
    ax.plot(
        xlin,
        ylin,
        linestyle="--",
        color="black",
        label="Linear fit",
    )

    ax.set_xlabel("Latitude")
    ax.set_ylabel("Temperature amplitude")
    ax.set_title("Relationship between latitude and temperature amplitude")
    ax.grid(True)

    plt.tight_layout()
    plt.show()

def temp_model(t, T0, A, phi):
    return T0 + A * np.sin(2 * np.pi * t / 365 + phi)

def curve_fit(df:pd.DataFrame)->None:
    t = np.arange(1, len(df) + 1)
    temperature = df["avg_daily_temp"]
    parameters, covariance = scipy.optimize.curve_fit(
                temp_model,
                t,
                temperature
            )
    T0, A, phi = parameters
    errors = np.sqrt(np.diag(covariance))
    rezultat = {
            "T0": T0,
            "A": A,
            "phi": phi,
            }
    out_file = open("rezult.json", "w")
    json.dump(rezultat, out_file, indent = 6)
    out_file.close()
    fitted_temperature = temp_model(t, T0, A, phi)
    
    plt.figure(figsize=(12, 5))
    plt.scatter(t, temperature, s=10, label="Observed data")
    plt.plot(t, fitted_temperature, color="red", label="Fitted model")
    plt.xlabel("Day of year")
    plt.ylabel("Mean temperature (°C)")
    plt.title("Seasonal temperature model")
    plt.legend()
    plt.grid(True)
    plt.show()

def get_city_photos(cities: list[City], URL_nasa:str):
    params = [make_params_nasa_sgl(city) for city in cities]
    print(params)
    city_photo_data = []
    for param, city in zip(params, cities):
        try:
            res = requests.get(URL_nasa, params=to_json_nasa(param), timeout=30)
            image = Image.open(BytesIO(res.content)).convert("RGB")
            image_array = np.asarray(image)
            city_photo_data.append({
                "city": city.name,
                "image": image_array,
                "mean_brightness": image_array.mean(),
            })
        except requests.exceptions.Timeout:
            print("The API request timed out.")
        except requests.exceptions.ConnectionError:
            print("Could not connect to the API.")
        except requests.exceptions.HTTPError as error:
            print(f"The API returned an HTTP error: {error}")
        except requests.exceptions.JSONDecodeError:
            print("The API response was not valid JSON.")
        except requests.exceptions.RequestException as error:
            print(f"An unexpected request error occurred: {error}")
    return city_photo_data


def amplitude_latitude_brightness_relationship(
    dfl: list[pd.DataFrame],
    city_photo_data
) -> None:
    amplitudes = []
    latitudes = []
    cities = []
    mean_brightness = []
    for df, city_image in zip(dfl, city_photo_data):
        amplitude = (
            df["avg_daily_temp"].max()
            - df["avg_daily_temp"].min()
        )

        amplitudes.append(amplitude)
        latitudes.append(df.attrs["latitude"])
        cities.append(df.attrs["city"])
        mean_brightness.append(city_image["mean_brightness"])
    data = sorted(
        zip(latitudes, amplitudes, cities, mean_brightness),
        key=lambda item: item[0],
    )

    latitudes, amplitudes, cities, mean_brightness = zip(*data)

    x = np.array(latitudes)
    y = np.array(amplitudes)
    z = np.array(mean_brightness)
    
    xi = np.linspace(x.min(), x.max(), 40)
    yi = np.linspace(y.min(), y.max(), 40)

    X, Y = np.meshgrid(xi, yi)

    Z = scipy.interpolate.griddata(
                points = (x, y),
                values = z,
                xi = (X, Y)
                method = "linear"
            )
    
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")

    surface = ax.plot_surface(
        X,
        Y,
        Z,
        cmap="viridis",
        edgecolor="none",
        alpha=0.8,
    )

    ax.scatter(
    x,
    y,
    z,
    color="red",
    s=40,
    label="Original points",
    )
    for latitude, amplitude, brightness, city in zip(
        x,
        y,
        z,
        cities,
    ):
        ax.text(
            latitude,
            amplitude,
            brightness,
            f"  {city}",
            fontsize=9,
            color="black",
        )

    ax.set_xlabel("Latitudes")
    ax.set_ylabel("Mean temperature aplitudes")
    ax.set_zlabel("Nightime Mean Brightness")
    ax.set_title("3D relationship between latitude, mean_temperature_aplitude and Nightime Brightness of cities")

    fig.colorbar(surface, ax=ax, shrink=0.6, )
    ax.legend()

    plt.show()

weatherParamsList, cities = make_params(cities, URL_cities)
df_array = [tdf(x, city) for x, city in zip(get_weather_for_cities(weatherParamsList, URL_weather), cities)]
#amplitude_latitude_relationship(df_array)
#curve_fit(df_array[2])
#plot_whtr_data_list(df_array)
city_data = get_city_photos(cities, URL_nasa)
print(city_data)
amplitude_latitude_brightness_relationship(df_array, city_data)


