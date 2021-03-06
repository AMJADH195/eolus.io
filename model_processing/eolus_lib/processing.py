from .config import config, models
from .logger import log
from . import file_tools as file_tools
from . import model_tools as model_tools
from . import pg_connection_manager as pg
from .http_manager import http

from datetime import datetime, timedelta, tzinfo, time
import os
import random
import requests

from osgeo import ogr, gdal, osr, gdalconst


def start(model_name, timestamp):

    formatted_timestamp = timestamp.strftime('%Y%m%d_%HZ')

    log(f"· Start processing {model_name} | {formatted_timestamp}.",
        "INFO", indentLevel=1, remote=True, model=model_name)

    try:
        conn, curr = pg.ConnectionPool.connect()
        curr.execute("UPDATE eolus4.models SET (status, timestamp, lastfh) = (%s, %s, %s) WHERE model = %s",
                     ("PROCESSING", timestamp, "0", model_name))
        conn.commit()

        curr.execute(
            "DELETE FROM eolus4.run_status WHERE model = %s AND timestamp = %s", (model_name, timestamp))
        conn.commit()

        curr.execute("INSERT INTO eolus4.run_status (model, status, timestamp) VALUES (%s, %s, %s)",
                     (model_name, "PROCESSING", timestamp))
        conn.commit()
        pg.ConnectionPool.close(conn, curr)
    except:
        pg.ConnectionPool.close(conn, curr)
        log("Could not set the model status back to processing! This requires manual intervention.",
            "ERROR", remote=True)
        return False

    return True


def model_can_be_processed(pool):
    for value in pool.values():
        if 'processing' in value and value['processing'] == True:
            return False

    return True


def process(processing_pool):

    choices = list(processing_pool.keys())
    random.shuffle(choices)
    model_name = None

    while len(choices) > 0:
        test_model_name = choices.pop()

        if model_can_be_processed(processing_pool[test_model_name]):
            model_name = test_model_name
            break

    if model_name == None:
        log("Not enough non-processing models right now.", "DEBUG")
        time.sleep(2)
        return False

    log("· Trying to process a step in model " + model_name, "INFO")

    pool_model = processing_pool[model_name]

    step = None
    steps = iter(pool_model)
    step = next(steps)

    pool_model[step]['processing'] = True
    full_fh = pool_model[step]['fh']
    band_num = pool_model[step]['band_num']

    log("Preparing to process " + model_name + " | fh: " + full_fh, "INFO")
    conn = None
    curr = None

    try:
        conn, curr = pg.ConnectionPool.connect()
        curr.execute(
            "SELECT timestamp FROM eolus4.models WHERE model = %s", (model_name,))
        timestamp = curr.fetchone()[0]
        log("· Timestamp retrieved", "DEBUG")

    except:
        pg.ConnectionPool.close(conn, curr)
        log("Couldn't get the timestamp for model " +
            model_name, "ERROR", remote=True)
        pool_model[step]['retries'] += 1
        pool_model[step]['processing'] = False

        if step['retries'] > config['maxRetriesPerStep']:
            del pool_model[step]
            if len(pool_model) == 0:
                del processing_pool[model_name]

        return False

    band = None
    band_info_str = ' | (no var/level)'
    if 'band' in pool_model[step]:
        band = pool_model[step]['band']
        band_info_str = ' | band ' + band['shorthand']

    file_exists = model_tools.check_if_model_fh_available(
        model_name, timestamp, full_fh)

    if not file_exists:
        log("Remote data not ready yet. " + model_name + " | fh: " +
            full_fh + band_info_str, 'NOTICE', remote=True, model=model_name)

        pool_model[step]['processing'] = False
        del processing_pool[model_name]
        try:
            curr.execute("UPDATE eolus4.models SET (status,lastfh,paused_at) = (%s, %s, %s) WHERE model = %s",
                         ("PAUSED", full_fh, datetime.now().isoformat(), model_name))
            conn.commit()

        except Exception as e:
            log(repr(e), "ERROR")

        pg.ConnectionPool.close(conn, curr)
        return False

    log("Processing for " + model_name + " | fh: " + full_fh +
        band_info_str, "NOTICE", remote=True, model=model_name)

    pg.ConnectionPool.close(conn, curr)

    try:
        if band is None:
            if not download_full_file(model_name, timestamp, full_fh, band_num):
                pool_model[step]['retries'] += 1
                pool_model[step]['processing'] = False
                if pool_model[step]['retries'] > config['maxRetriesPerStep']:
                    del pool_model[step]
                    if len(pool_model) == 0:
                        end(model_name)
                        del processing_pool[model_name]
                return False
        else:
            if not download_band(model_name, timestamp, full_fh, band, band_num):
                pool_model[step]['retries'] += 1
                pool_model[step]['processing'] = False
                if pool_model[step]['retries'] > config['maxRetriesPerStep']:
                    del pool_model[step]
                    if len(pool_model) == 0:
                        end(model_name)
                        del processing_pool[model_name]
                return False

        log("Successfully processed " + model_name +
            " | fh: " + full_fh + band_info_str, "NOTICE")

        if step in pool_model:
            del pool_model[step]
        if len(pool_model) == 0:
            end(model_name)
            del processing_pool[model_name]
        return True
    except Exception as e:
        log("Failure.", "ERROR", remote=True)
        log(repr(e), "ERROR", indentLevel=2, remote=True, model=model_name)
        if step in pool_model:
            pool_model[step]['retries'] += 1
            pool_model[step]['processing'] = False
            if pool_model[step]['retries'] > config['maxRetriesPerStep']:
                del pool_model[step]
                if len(pool_model) == 0:
                    del processing_pool[model_name]
        return False


'''
    Uses an .idx file to download an individual band and convert it to a TIF library.
'''


def download_band(model_name, timestamp, fh, band, band_num):
    model = models[model_name]

    url = model_tools.make_url(model_name, timestamp.strftime(
        "%Y%m%d"), timestamp.strftime("%H"), fh)

    file_name = model_tools.get_base_filename(
        model_name, timestamp, band["shorthand"])
    target_dir = config["mapfileDir"] + "/" + model_name + "/"
    target_raw_dir = config["mapfileDir"] + "/rawdata/" + model_name + "/"
    download_filename = config["tempDir"] + "/" + \
        file_name + "_t" + fh + "." + model["filetype"]
    target_filename = target_dir + file_name + ".tif"
    target_raw_filename = target_raw_dir + file_name + ".tif"

    try:
        response = requests.head(url)
        if response.status_code != 200 or response.status_code == None or response == None:
            log(f"· This index file is not ready yet. " + url,
                "WARN", remote=True, indentLevel=2, model=model_name)
            return False

        content_length = str(response.headers["Content-Length"])
    except Exception as e:
        log(f"· Couldn't get header of " + url, "ERROR",
            remote=True, indentLevel=2, model=model_name)
        log(repr(e), "ERROR")
        return False

    byte_range = get_byte_range(band, url + ".idx", content_length)

    if not byte_range or byte_range == None:
        log(f"· Band {band['shorthand']} doesn't exist for fh {fh}.",
            "WARN", remote=True, indentLevel=2, model=model_name)
        return False

    log(f"↓ Downloading band {band['shorthand']} for fh {fh}.",
        "INFO", indentLevel=2, remote=True, model=model_name)
    try:
        response = http.request('GET', url,
                                headers={
                                    'Range': 'bytes=' + byte_range
                                },
                                retries=5)

        f = open(download_filename, 'wb')
        f.write(response.data)
        f.close()
    except:
        log("Couldn't read the band -- the request likely timed out. " +
            fh, "ERROR", indentLevel=2, remote=True, model=model_name)
        return False

    log(f"✓ Downloaded band {band['shorthand']} for fh {fh}.",
        "INFO", indentLevel=2, remote=True, model=model_name)

    bounds = config["bounds"][model["bounds"]]
    width = model["imageWidth"]

    epsg4326 = osr.SpatialReference()
    epsg4326.ImportFromEPSG(4326)

    log("· Warping downloaded data.", "INFO",
        indentLevel=2, remote=True, model=model_name)
    try:
        grib_file = gdal.Open(download_filename)
        out_file = gdal.Warp(
            download_filename + ".tif",
            grib_file,
            format='GTiff',
            outputBounds=[bounds["left"], bounds["bottom"],
                          bounds["right"], bounds["top"]],
            dstSRS=epsg4326,
            width=width,
            resampleAlg=gdal.GRA_CubicSpline)
        out_file.FlushCache()
        out_file = None

        out_file = gdal.Warp(
            download_filename + "_unscaled.tif",
            grib_file,
            format='GTiff',
            outputBounds=[bounds["left"], bounds["bottom"],
                          bounds["right"], bounds["top"]],
            dstSRS=epsg4326,
            creationOptions=["COMPRESS=deflate", "ZLEVEL=9"],
            resampleAlg=gdal.GRA_CubicSpline)
        out_file.FlushCache()
        out_file = None

        grib_file = None
    except Exception as e:
        log("Warping failed -- " + download_filename, "ERROR", remote=True)
        log(repr(e), "ERROR", indentLevel=2, remote=True, model=model_name)
        return False

    # check to see if the working raster exists
    if not os.path.exists(target_filename):
        log(f"· Creating output master TIF | {target_filename}",
            "INFO", indentLevel=2, remote=True, model=model_name)
        try:
            os.makedirs(target_dir)
        except:
            log("· Directory already exists.", "INFO",
                indentLevel=2, remote=False, model=model_name)

        num_bands = model_tools.get_number_of_hours(model_name)

        try:
            grib_file = gdal.Open(download_filename + ".tif")
            geo_transform = grib_file.GetGeoTransform()
            width = grib_file.RasterXSize
            height = grib_file.RasterYSize

            new_raster = gdal.GetDriverByName('MEM').Create(
                '', width, height, num_bands, gdal.GDT_Float32)
            new_raster.SetProjection(grib_file.GetProjection())
            new_raster.SetGeoTransform(list(geo_transform))
            gdal.GetDriverByName('GTiff').CreateCopy(
                target_filename, new_raster, 0)
            log("✓ Output master TIF created --> " + target_filename, "NOTICE",
                indentLevel=1, remote=True, model=model_name)
            new_raster = None
            grib_file = None
        except Exception as e:
            log("Couldn't create the new master TIF: " + target_filename,
                "ERROR", indentLevel=1, remote=True, model=model_name)
            log(repr(e), "ERROR", indentLevel=2, remote=True, model=model_name)
            return False

    # check to see if the working raster exists
    if not os.path.exists(target_raw_filename):
        log(f"· Creating output master TIF | {target_raw_filename}",
            "INFO", indentLevel=2, remote=True, model=model_name)
        try:
            os.makedirs(target_raw_dir)
        except:
            log("· Directory already exists.", "INFO",
                indentLevel=2, remote=False, model=model_name)

        num_bands = model_tools.get_number_of_hours(model_name)

        try:
            grib_file = gdal.Open(download_filename + "_unscaled.tif")
            geo_transform = grib_file.GetGeoTransform()
            width = grib_file.RasterXSize
            height = grib_file.RasterYSize

            new_raster = gdal.GetDriverByName('MEM').Create(
                '', width, height, num_bands, gdal.GDT_Float32)
            new_raster.SetProjection(grib_file.GetProjection())
            new_raster.SetGeoTransform(list(geo_transform))
            gdal.GetDriverByName('GTiff').CreateCopy(
                target_raw_filename, new_raster, 0)
            log("✓ Output master TIF created --> " + target_raw_filename, "NOTICE",
                indentLevel=1, remote=True, model=model_name)
            new_raster = None
            grib_file = None
        except Exception as e:
            log("Couldn't create the new master TIF: " + target_raw_filename,
                "ERROR", indentLevel=2, remote=True, model=model_name)
            log(repr(e), "ERROR", indentLevel=2, remote=True, model=model_name)
            return False

    log(f"· Writing data to the GTiff | band: {band['shorthand']} | fh: {fh} | band_number: {str(band_num)}",
        "INFO", indentLevel=2, remote=True, model=model_name)

    sub_band_num = 1
    if "subBandNum" in band["band"]:
        sub_band_num = band["band"]["subBandNum"]

    try:
        # Copy the downloaded band to this temp file
        grib_file = gdal.Open(download_filename + ".tif")
        data = grib_file.GetRasterBand(sub_band_num).ReadAsArray()

        tif = gdal.Open(target_filename, gdalconst.GA_Update)
        tif.GetRasterBand(band_num).WriteArray(data)
        tif.FlushCache()

        grib_file = gdal.Open(download_filename + "_unscaled.tif")
        data = grib_file.GetRasterBand(sub_band_num).ReadAsArray()

        tif = gdal.Open(target_raw_filename, gdalconst.GA_Update)
        tif.GetRasterBand(band_num).WriteArray(data)
        tif.FlushCache()

        grib_file = None
        tif = None
        data = None
        log(f"✓ Data written to the GTiff | band: {band['shorthand']} | fh: {fh}.",
            "INFO", indentLevel=2, remote=True, model=model_name)
    except Exception as e:
        log(f"Couldn't write band to TIF | band: {band['shorthand']} | fh: {fh}.",
            "ERROR", indentLevel=2, remote=True, model=model_name)
        log(repr(e), "ERROR", indentLevel=2, remote=True, model=model_name)
        return False

    try:
        os.remove(download_filename)
        os.remove(download_filename + ".tif")
        os.remove(download_filename + "_unscaled.tif")
    except:
        log(f"× Could not delete a temp file ({download_filename}).",
            "WARN", indentLevel=2, remote=True, model=model_name)

    return True


'''
    Downloads a full GRIB2 file for a timestamp, then extracts each var/level
    to convert to separate TIF libraries.
'''


def download_full_file(model_name, timestamp, fh, band_num):
    model = models[model_name]

    url = model_tools.make_url(model_name, timestamp.strftime(
        "%Y%m%d"), timestamp.strftime("%H"), fh)

    file_name = model_tools.get_base_filename(model_name, timestamp, None)
    target_dir = config["mapfileDir"] + "/" + model_name + "/"
    target_raw_dir = config["mapfileDir"] + "/rawdata/" + model_name + "/"
    download_filename = config["tempDir"] + "/" + \
        file_name + "_t" + fh + "." + model["filetype"]

    try:
        os.makedirs(target_dir)
    except:
        log("· Directory already exists.", "INFO",
            indentLevel=2, remote=False, model=model_name)

    try:
        os.makedirs(target_raw_dir)
    except:
        log("· Directory already exists.", "INFO",
            indentLevel=2, remote=False, model=model_name)

    log(f"↓ Downloading fh {fh}.", "INFO",
        indentLevel=2, remote=True, model=model_name)
    try:
        response = http.request('GET', url, retries=5)
        log("Url: " + url, "DEBUG", indentLevel=2)
        log("Download: " + download_filename, "DEBUG", indentLevel=2)

        f = open(download_filename, 'wb')
        f.write(response.data)
        f.close()
        log(f"✓ Downloaded band fh {fh}.", "INFO",
            indentLevel=2, remote=True, model=model_name)
    except Exception as e:
        log("Couldn't read the fh -- the request likely timed out. " +
            fh, "ERROR", indentLevel=2, remote=True, model=model_name)
        log(repr(e), "ERROR", indentLevel=2, remote=True, model=model_name)
        return False

    bounds = config["bounds"][model["bounds"]]
    width = model["imageWidth"]

    try:
        epsg4326 = osr.SpatialReference()
        epsg4326.ImportFromEPSG(4326)

        log("· Warping downloaded data.", "INFO",
            indentLevel=2, remote=True, model=model_name)
        try:
            os.remove(download_filename + ".tif")
        except:
            log("· No old file to remove.", "DEBUG", indentLevel=2)

        grib_file = gdal.Open(download_filename)
        out_file = gdal.Warp(
            download_filename + ".tif",
            grib_file,
            format='GTiff',
            outputBounds=[bounds["left"], bounds["bottom"],
                          bounds["right"], bounds["top"]],
            dstSRS=epsg4326,
            width=width,
            resampleAlg=gdal.GRA_CubicSpline)
        out_file.FlushCache()

        out_file = gdal.Warp(
            download_filename + "_unscaled.tif",
            grib_file,
            format='GTiff',
            outputBounds=[bounds["left"], bounds["bottom"],
                          bounds["right"], bounds["top"]],
            dstSRS=epsg4326,
            creationOptions=["COMPRESS=deflate", "ZLEVEL=9"],
            resampleAlg=gdal.GRA_CubicSpline)
        out_file.FlushCache()

        out_file = None
        grib_file = None

    except Exception as e:
        log("Warping failed -- " + download_filename, "ERROR",
            indentLevel=2, remote=True, model=model_name)
        log(repr(e), "ERROR", indentLevel=2, remote=True, model=model_name)
        return False

    num_bands = model_tools.get_number_of_hours(model_name)

    bands = model_tools.make_model_band_array(model_name, force=True)
    if bands == None:
        try:
            os.makedirs(target_dir)
        except:
            log("· Directory already exists.", "INFO",
                indentLevel=2, remote=True, model=model_name)

        try:
            os.makedirs(target_raw_dir)
        except:
            log("· Directory already exists.", "INFO",
                indentLevel=2, remote=False, model=model_name)

        target_filename = target_dir + \
            model_tools.get_base_filename(
                model_name, timestamp, None) + "_t" + fh + ".tif"
        target_raw_filename = target_raw_dir + \
            model_tools.get_base_filename(
                model_name, timestamp, None) + "_t" + fh + ".tif"
        log("· Copying to " + target_filename, "INFO",
            indentLevel=2, remote=True, model=model_name)

        try:
            shutil.copyfile(download_filename + ".tif", target_filename)
            shutil.copyfile(download_filename +
                            "_unscaled.tif", target_raw_filename)
        except:
            log("Couldn't copy.", "ERROR", indentLevel=2,
                remote=True, model=model_name)
            return False

    else:
        log(f"· Extracting bands for fh {fh}.", "INFO",
            indentLevel=2, remote=True, model=model_name)

        for band in bands:
            target_filename = target_dir + \
                model_tools.get_base_filename(
                    model_name, timestamp, band["shorthand"]) + ".tif"
            target_raw_filename = target_raw_dir + \
                model_tools.get_base_filename(
                    model_name, timestamp, band["shorthand"]) + ".tif"
            if not os.path.exists(target_filename):
                log(f"· Creating output master TIF with {str(num_bands) } bands | {target_filename}",
                    "INFO", indentLevel=2, remote=True, model=model_name)
                try:
                    os.makedirs(target_dir)
                except:
                    log("· Directory already exists.", "INFO",
                        indentLevel=2, remote=True, model=model_name)

                try:
                    grib_file = gdal.Open(download_filename + ".tif")
                    geo_transform = grib_file.GetGeoTransform()
                    width = grib_file.RasterXSize
                    height = grib_file.RasterYSize

                    new_raster = gdal.GetDriverByName('MEM').Create(
                        '', width, height, num_bands, gdal.GDT_Float32)
                    new_raster.SetProjection(grib_file.GetProjection())
                    new_raster.SetGeoTransform(list(geo_transform))
                    gdal.GetDriverByName('GTiff').CreateCopy(
                        target_filename, new_raster, 0)
                    grib_file = None
                    new_raster = None
                    log("✓ Output master TIF created. --> " + target_filename, "NOTICE",
                        indentLevel=1, remote=True, model=model_name)
                except:
                    log("Couldn't create the new master TIF. --> " + target_filename, "ERROR",
                        indentLevel=1, remote=True, model=model_name)
                    return False

            if not os.path.exists(target_raw_filename):
                log(f"· Creating output master TIF with {str(num_bands) } bands | {target_raw_filename}",
                    "INFO", indentLevel=2, remote=True, model=model_name)
                try:
                    os.makedirs(target_raw_dir)
                except:
                    log("· Directory already exists.", "INFO",
                        indentLevel=2, remote=False, model=model_name)

                try:
                    grib_file = gdal.Open(download_filename + "_unscaled.tif")
                    geo_transform = grib_file.GetGeoTransform()
                    width = grib_file.RasterXSize
                    height = grib_file.RasterYSize

                    new_raster = gdal.GetDriverByName('MEM').Create(
                        '', width, height, num_bands, gdal.GDT_Float32)
                    new_raster.SetProjection(grib_file.GetProjection())
                    new_raster.SetGeoTransform(list(geo_transform))
                    gdal.GetDriverByName('GTiff').CreateCopy(
                        target_raw_filename, new_raster, 0)
                    grib_file = None
                    new_raster = None
                    log("✓ Output master TIF created.  --> " + target_raw_filename, "NOTICE",
                        indentLevel=1, remote=True, model=model_name)
                except:
                    log("Couldn't create the new master TIF. --> " + target_raw_filename, "ERROR",
                        indentLevel=1, remote=True, model=model_name)
                    return False

            log(f"· Writing data to the GTiff | band: {band['shorthand']} | fh: {fh}",
                "INFO", indentLevel=2, remote=True, model=model_name)
            # Copy the downloaded band to this temp file
            try:
                grib_file = gdal.Open(download_filename + ".tif")
                gribnum_bands = grib_file.RasterCount
                band_level = model_tools.get_level_name_for_level(
                    band["band"]["level"], "gribName")
                tif = gdal.Open(target_filename, gdalconst.GA_Update)
                for i in range(1, gribnum_bands + 1):
                    try:
                        file_band = grib_file.GetRasterBand(i)
                        metadata = file_band.GetMetadata()
                        if metadata["GRIB_ELEMENT"].lower() == band["band"]["var"].lower() and metadata["GRIB_SHORT_NAME"].lower() == band_level.lower():
                            log("· Band " + band["band"]["var"] + " found.",
                                "DEBUG", indentLevel=2, remote=False)
                            data = file_band.ReadAsArray()
                            tif.GetRasterBand(band_num).WriteArray(data)
                            break

                    except Exception as e:
                        log(f"× Couldn't read GTiff band: #{str(i)} | fh: {fh}",
                            "WARN", indentLevel=2, remote=True, model=model_name)
                        log(repr(e), "ERROR")

                tif.FlushCache()

                grib_file = gdal.Open(download_filename + "_unscaled.tif")
                tif = gdal.Open(target_raw_filename, gdalconst.GA_Update)
                for i in range(1, gribnum_bands + 1):
                    try:
                        file_band = grib_file.GetRasterBand(i)
                        metadata = file_band.GetMetadata()
                        if metadata["GRIB_ELEMENT"].lower() == band["band"]["var"].lower() and metadata["GRIB_SHORT_NAME"].lower() == band_level.lower():
                            log("· Band " + band["band"]["var"] + " found.",
                                "DEBUG", indentLevel=2, remote=False)
                            data = file_band.ReadAsArray()
                            tif.GetRasterBand(band_num).WriteArray(data)
                            break

                    except Exception as e:
                        log(f"× Couldn't read GTiff band: #{str(i)} | fh: {fh}",
                            "WARN", indentLevel=2, remote=True, model=model_name)
                        log(repr(e), "ERROR")

                tif.FlushCache()
                grib_file = None
                tif = None
                data = None
            except Exception as e:
                return False

    try:
        os.remove(download_filename)
        os.remove(download_filename + ".tif")
        os.remove(download_filename + "_unscaled.tif")
    except:
        log(f"× Could not delete a temp file ({download_filename}).",
            "WARN", indentLevel=2, remote=True, model=model_name)

    return True


def end(model_name):

    file_tools.clean()
    pg.clean()

    try:
        conn, curr = pg.ConnectionPool.connect()
        log("✓ " + model_name + " is completely finished processing.",
            "NOTICE", remote=True, model=model_name)
        curr.execute(
            "UPDATE eolus4.models SET status = %s WHERE model = %s", ("WAITING", model_name))
        conn.commit()
        model_tools.update_run_status(model_name)
        pg.ConnectionPool.close(conn, curr)
    except Exception as e:
        log(repr(e), "ERROR")
        pg.ConnectionPool.close(conn, curr)
        log("Couldn't mark model as complete.",
            "ERROR", remote=True, model=model_name)


'''
    Copied a bit from https://github.com/cacraig/grib-inventory/ - thanks!
'''


def get_byte_range(band, idx_file, content_length):
    log(f"· Searching for band defs in index file {idx_file}",
        "DEBUG", indentLevel=2, remote=True)
    try:
        response = http.request('GET', idx_file)
        data = response.data.decode('utf-8')
        var_name_to_find = band["band"]["var"]
        level_to_find = model_tools.get_level_name_for_level(
            band["band"]["level"], "idxName")
        found = False
        start_byte = None
        end_byte = None
        skipped_for_subband = False

        for line in data.splitlines():
            line = str(line)
            parts = line.split(':')
            var_name = parts[3]
            level = parts[4]
            time = parts[5]

            if found:
                if "subBandNum" in band["band"] and band["band"]["subBandNum"] and not skipped_for_subband:
                    skipped_for_subband = True
                else:
                    end_byte = parts[1]
                    break

            if var_name == var_name_to_find and level == level_to_find:
                if "time_range" in band["band"]:
                    range_val = time.split(" ", 1)[0]
                    ranges = range_val.split("-")
                    if (int(ranges[1]) - int(ranges[0])) != band["band"]["time_range"]:
                        continue

                if "time" in band:
                    hr = time.split(" ", 1)[0]
                    if "-" in hr:
                        hr = hr.split("-")[1]

                    if hr != band["time"]:
                        continue

                log("✓ Found.", "DEBUG", indentLevel=2, remote=False)
                found = True
                start_byte = parts[1]
                continue

        if found:
            if end_byte == None:
                end_byte = content_length

            log(f"· Bytes {start_byte} to {end_byte}", "DEBUG", indentLevel=2)
            if start_byte == end_byte:
                return None

            return start_byte + "-" + end_byte
        else:
            log(f"· Couldn't find band def in index file.",
                "WARN", indentLevel=2, remote=True)
        return None

    except Exception as e:
        log(f"Band def retrieval failed.", "ERROR", indentLevel=2, remote=True)
        log(repr(e), "ERROR")
        return None
