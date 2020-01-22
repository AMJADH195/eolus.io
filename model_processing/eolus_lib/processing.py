from .config import config, models
from .logger import log
from . import file_tools as file_tools
from . import model_tools as model_tools
from . import pg_connection_manager as pg

from datetime import datetime, timedelta, tzinfo, time
import os


def start(model_name, timestamp):

    formatted_timestamp = timestamp.strftime('%Y%m%d_%HZ')

    log(f"· Started processing {model_name} | {formatted_timestamp}.",
        "INFO", indentLevel=1, remote=True, model=model_name)

    try:
        pg.ConnectionPool.curr.execute("UPDATE eolus3.models SET (status, timestamp) = (%s, %s) WHERE model = %s",
                                       ("PROCESSING", timestamp, model_name))
        pg.ConnectionPool.conn.commit()

        pg.ConnectionPool.curr.execute(
            "DELETE FROM eolus3.run_status WHERE model = %s AND timestamp = %s", (model_name, timestamp))
        pg.ConnectionPool.conn.commit()

        pg.ConnectionPool.curr.execute("INSERT INTO eolus3.run_status (model, status, timestamp) VALUES (%s, %s, %s)",
                                       (model_name, "PROCESSING", timestamp))
        pg.ConnectionPool.conn.commit()
    except:
        pg.reset()
        log("Could not set the model status back to processing! This requires manual intervention.",
            "ERROR", remote=True)
        return False

    return True


def find_model_step_to_process(model_name):
    found = False
    model = models[model_name]
    fh = model["startTime"]
    orig_band = -1

    try:
        pg.ConnectionPool.curr.execute(
            "SELECT timestamp FROM eolus3.models WHERE model = %s", (model_name,))
        timestamp = pg.ConnectionPool.curr.fetchone()[0]

        formatted_timestamp = timestamp.strftime('%Y%m%d_%HZ')
        table_name = model_name + "_" + formatted_timestamp

    except:
        pg.reset()
        log("Couldn't get the timetamp for model " +
            model_name, "ERROR", remote=True)

    try:
        # TODO PUT LIKE WHERE fh, grib_var, band not in whatever is currently in model_processing_pool
        pg.ConnectionPool.curr.execute("SELECT fh, grib_var, band FROM eolus3." + table_name +
                                       " WHERE status = 'WAITING' ORDER BY band ASC LIMIT 1")
        res = pg.ConnectionPool.curr.fetchone()
        if not res or len(res) == 0:
            return False
        full_fh = res[0]
        grib_var = res[1]
        orig_band = res[2]

    except:
        pg.reset()
        log("Couldn't get the status of a timestep from " +
            table_name, "ERROR", remote=True)
        return False

    band = None

    if not grib_var:
        band = None
    else:
        model_band_array = make_model_band_array(model_name)
        for bandItem in model_band_array:
            if bandItem["shorthand"] == grib_var:
                band = bandItem
                break

    band_str = ""
    if band:
        band_str = " AND grib_var = '" + band["shorthand"] + "'"

    band_info_str = ""
    if band is not None:
        band_info_str = " | Band: " + band["shorthand"]

    try:
        pg.ConnectionPool.curr.execute("UPDATE eolus3." + table_name + " SET (status, start_time, agent) = (%s, %s, %s) WHERE fh = %s" +
                                       band_str, ("PROCESSING", datetime.utcnow(), pid, full_fh))
        pg.ConnectionPool.conn.commit()
    except:
        pg.reset()
        log("Couldn't set a status to processing in " +
            table_name, "ERROR", remote=True)

    log("· Attempting to process fh " + full_fh + band_info_str,
        "INFO", remote=True, indentLevel=1, model=model_name)
    processed = process(model_name, table_name, full_fh, timestamp, band)

    if processed:
        log("✓ Done.", "INFO", remote=True, indentLevel=1, model=model_name)
        return True

    else:
        try:
            log("· Setting back to waiting.", "INFO",
                remote=True, indentLevel=1, model=model_name)
            if grib_var is not None:
                pg.ConnectionPool.curr.execute("SELECT * FROM eolus3." + table_name +
                                               " WHERE fh = '" + full_fh + "' AND grib_var = '" + grib_var + "'")
            else:
                pg.ConnectionPool.curr.execute("SELECT * FROM eolus3." +
                                               table_name + " WHERE fh = '" + full_fh + "'")
            res = pg.ConnectionPool.curr.fetchone()

            if not res or len(res) == 0:
                pg.ConnectionPool.curr.execute("INSERT INTO eolus3." + table_name +
                                               " (fh, status, band, grib_var) VALUES (%s,%s,%s,%s)", (full_fh, "WAITING", orig_band, grib_var))
                pg.ConnectionPool.conn.commit()

            else:
                pg.ConnectionPool.curr.execute("UPDATE eolus3." + table_name + " SET (status, start_time) = (%s, %s) WHERE fh = %s" +
                                               band_str, ("WAITING", datetime.utcnow(), full_fh))
                pg.ConnectionPool.conn.commit()
        except Exception as e:
            pg.reset()
            log("Couldn't set a status to back to waiting in " + table_name +
                "... This will need manual intervention.", "ERROR", remote=True)
            log(repr(e), "ERROR", indentLevel=2, remote=True, model=model_name)
        return False


def download_band(model_name, timestamp, fh, band, table_name):
    model = models[model_name]

    try:
        pg.ConnectionPool.curr.execute("SELECT band FROM eolus3." +
                                       table_name + " WHERE fh = %s", (fh,))
        band_number = pg.ConnectionPool.curr.fetchone()[0]
    except:
        pg.reset()
        log("Couldn't get the next band to process, fh " + fh + ", table " +
            table_name, "ERROR", remote=True, indentLevel=2, model=model_name)
        return False

    url = model_tools.make_url(model_name, timestamp.strftime(
        "%Y%m%d"), timestamp.strftime("%H"), fh)

    file_name = model_tools.get_base_filename(model_name, timestamp, band)
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
    except:
        log(f"· Couldn't get header of " + url, "ERROR",
            remote=True, indentLevel=2, model=model_name)
        return False

    byte_range = getbyte_range(band, url + ".idx", content_length)

    if not byte_range or byte_range == None:
        log(f"· Band {band['shorthand']} doesn't exist for fh {fh}.",
            "WARN", remote=True, indentLevel=2, model=model_name)
        try:
            pg.ConnectionPool.curr.execute("DELETE FROM eolus3." + table_name +
                                           " WHERE fh = %s AND grib_var = %s", (fh, band["shorthand"]))
            pg.ConnectionPool.conn.commit()
        except:
            pg.reset()
            log("Couldn't delete an unusable band from the table. " + fh + ", table " +
                table_name, "ERROR", remote=True, indentLevel=2, model=model_name)
        return True

    log(f"↓ Downloading band {band['shorthand']} for fh {fh}.",
        "NOTICE", indentLevel=2, remote=True, model=model_name)
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
        log("Couldn't read the band -- the request likely timed out. " + fh +
            ", table " + table_name, "ERROR", indentLevel=2, remote=True, model=model_name)
        return False

    log(f"✓ Downloaded band {band['shorthand']} for fh {fh}.",
        "NOTICE", indentLevel=2, remote=True, model=model_name)

    bounds = config["bounds"][model["bounds"]]
    width = model["imageWidth"]

    epsg4326 = osr.SpatialReference()
    epsg4326.ImportFromEPSG(4326)

    log("· Warping downloaded data.", "NOTICE",
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
            "NOTICE", indentLevel=2, remote=True, model=model_name)
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
            log("✓ Output master TIF created.", "NOTICE",
                indentLevel=2, remote=True, model=model_name)
        except Exception as e:
            log("Couldn't create the new TIF: " + target_filename,
                "ERROR", indentLevel=2, remote=True, model=model_name)
            log(repr(e), "ERROR", indentLevel=2, remote=True, model=model_name)
            return False

    # check to see if the working raster exists
    if not os.path.exists(target_raw_filename):
        log(f"· Creating output master TIF | {target_raw_filename}",
            "NOTICE", indentLevel=2, remote=True, model=model_name)
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
            log("✓ Output master TIF created.", "NOTICE",
                indentLevel=2, remote=True, model=model_name)
        except Exception as e:
            log("Couldn't create the new TIF: " + target_raw_filename,
                "ERROR", indentLevel=2, remote=True, model=model_name)
            log(repr(e), "ERROR", indentLevel=2, remote=True, model=model_name)
            return False

    log(f"· Writing data to the GTiff | band: {band['shorthand']} | fh: {fh} | band_number: {str(band_number)}",
        "NOTICE", indentLevel=2, remote=True, model=model_name)

    try:
        # Copy the downloaded band to this temp file
        grib_file = gdal.Open(download_filename + ".tif")
        data = grib_file.GetRasterBand(1).ReadAsArray()

        tif = gdal.Open(target_filename, gdalconst.GA_Update)
        tif.GetRasterBand(band_number).WriteArray(data)
        tif.FlushCache()

        grib_file = gdal.Open(download_filename + "_unscaled.tif")
        data = grib_file.GetRasterBand(1).ReadAsArray()

        tif = gdal.Open(target_raw_filename, gdalconst.GA_Update)
        tif.GetRasterBand(band_number).WriteArray(data)
        tif.FlushCache()

        grib_file = None
        tif = None
        log(f"✓ Data written to the GTiff | band: {band['shorthand']} | fh: {fh}.",
            "NOTICE", indentLevel=2, remote=True, model=model_name)
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

    try:
        pg.ConnectionPool.curr.execute("DELETE FROM eolus3." + table_name +
                                       " WHERE fh = %s AND grib_var = %s", (fh, band["shorthand"]))
        pg.ConnectionPool.conn.commit()
    except:
        pg.reset()
        log("Couldn't update the DB that this band was processed.",
            "ERROR", indentLevel=2, remote=True, model=model_name)
        return False

    return True


'''
    Copied a bit from https://github.com/cacraig/grib-inventory/ - thanks!
'''


def get_byte_range(band, idxFile, content_length):
    log(f"· Searching for band defs in index file {idxFile}",
        "DEBUG", indentLevel=2, remote=True)
    try:
        response = http.request('GET', idxFile)
        data = response.data.decode('utf-8')
        var_name_to_find = band["band"]["var"]
        level_to_find = getLevelNameForLevel(band["band"]["level"], "idxName")
        found = False
        start_byte = None
        end_byte = None

        for line in data.splitlines():
            line = str(line)
            parts = line.split(':')
            var_name = parts[3]
            level = parts[4]
            time = parts[5]

            if found:
                end_byte = parts[1]
                break

            if var_name == var_name_to_find and level == level_to_find:
                if "timeRange" in band["band"].keys():
                    range_val = time.split(" ", 1)[0]
                    ranges = range_val.split("-")
                    if (int(ranges[1]) - int(ranges[0])) != band["band"]["timeRange"]:
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

    except:
        log(f"Band def retrieval failed.", "ERROR", indentLevel=2, remote=True)
        return None


def download_full_file(model_name, timestamp, fh, table_name):
    model = models[model_name]
    try:
        pg.ConnectionPool.curr.execute("SELECT band FROM eolus3." +
                                       table_name + " WHERE fh = %s", (fh,))
        band_number = pg.ConnectionPool.curr.fetchone()[0]
    except:
        pg.reset()
        log("Couldn't get the next fh to process, fh " + fh + ", table " +
            table_name, "ERROR", remote=True, indentLevel=2, model=model_name)
        return False

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

    log(f"↓ Downloading fh {fh}.", "NOTICE",
        indentLevel=2, remote=True, model=model_name)
    try:
        response = http.request('GET', url, retries=5)

        f = open(download_filename, 'wb')
        f.write(response.data)
        f.close()
        log(f"✓ Downloaded band fh {fh}.", "NOTICE",
            indentLevel=2, remote=True, model=model_name)
    except:
        log("Couldn't read the fh -- the request likely timed out. " + fh +
            ", table " + table_name, "ERROR", indentLevel=2, remote=True, model=model_name)
        return False

    bounds = config["bounds"][model["bounds"]]
    width = model["imageWidth"]

    try:
        epsg4326 = osr.SpatialReference()
        epsg4326.ImportFromEPSG(4326)

        log("· Warping downloaded data.", "NOTICE",
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

    except:
        log("Warping failed -- " + download_filename, "ERROR",
            indentLevel=2, remote=True, model=model_name)
        return False

    num_bands = model_tools.get_number_of_hours(model_name)

    bands = make_model_band_array(model_name, force=True)
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
        log("· Copying to " + target_filename, "NOTICE",
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
                    model_name, timestamp, band) + ".tif"
            target_raw_filename = target_raw_dir + \
                model_tools.get_base_filename(
                    model_name, timestamp, band) + ".tif"
            if not os.path.exists(target_filename):
                log(f"· Creating output master TIF with {str(num_bands) } bands | {target_filename}",
                    "NOTICE", indentLevel=2, remote=True, model=model_name)
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
                    log("✓ Output master TIF created.", "NOTICE",
                        indentLevel=2, remote=True, model=model_name)
                except:
                    log("Couldn't create the new TIF.", "ERROR",
                        indentLevel=2, remote=True, model=model_name)
                    return False

            if not os.path.exists(target_raw_filename):
                log(f"· Creating output master TIF with {str(num_bands) } bands | {target_raw_filename}",
                    "NOTICE", indentLevel=2, remote=True, model=model_name)
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
                    log("✓ Output master TIF created.", "NOTICE",
                        indentLevel=2, remote=True, model=model_name)
                except:
                    log("Couldn't create the new TIF.", "ERROR",
                        indentLevel=2, remote=True, model=model_name)
                    return False

            log(f"· Writing data to the GTiff | band: {band['shorthand']} | fh: {fh}",
                "NOTICE", indentLevel=2, remote=True, model=model_name)
            # Copy the downloaded band to this temp file
            try:
                grib_file = gdal.Open(download_filename + ".tif")
                gribnum_bands = grib_file.RasterCount
                bandLevel = model_tools.get_level_name_for_level(
                    band["band"]["level"], "gribName")
                tif = gdal.Open(target_filename, gdalconst.GA_Update)
                for i in range(1, gribnum_bands + 1):
                    try:
                        fileBand = grib_file.GetRasterBand(i)
                        metadata = fileBand.GetMetadata()
                        if metadata["GRIB_ELEMENT"].lower() == band["band"]["var"].lower() and metadata["GRIB_SHORT_NAME"].lower() == bandLevel.lower():
                            log("· Band " + band["band"]["var"] + " found.",
                                "DEBUG", indentLevel=2, remote=False)
                            data = fileBand.ReadAsArray()
                            tif.GetRasterBand(band_number).WriteArray(data)
                            break

                    except:
                        log(f"× Couldn't read GTiff band: #{str(i)} | fh: {fh}",
                            "WARN", indentLevel=2, remote=True, model=model_name)

                tif.FlushCache()

                grib_file = gdal.Open(download_filename + "_unscaled.tif")
                tif = gdal.Open(target_raw_filename, gdalconst.GA_Update)
                for i in range(1, gribnum_bands + 1):
                    try:
                        fileBand = grib_file.GetRasterBand(i)
                        metadata = fileBand.GetMetadata()
                        if metadata["GRIB_ELEMENT"].lower() == band["band"]["var"].lower() and metadata["GRIB_SHORT_NAME"].lower() == bandLevel.lower():
                            log("· Band " + band["band"]["var"] + " found.",
                                "DEBUG", indentLevel=2, remote=False)
                            data = fileBand.ReadAsArray()
                            tif.GetRasterBand(band_number).WriteArray(data)
                            break

                    except:
                        log(f"× Couldn't read GTiff band: #{str(i)} | fh: {fh}",
                            "WARN", indentLevel=2, remote=True, model=model_name)

                tif.FlushCache()
                grib_file = None
                tif = None
            except Exception as e:
                log("Couldn't write bands to the tiff. " + fh + ", table " +
                    table_name, "ERROR", indentLevel=2, remote=True, model=model_name)
                log(repr(e), "ERROR", indentLevel=2,
                    remote=True, model=model_name)
                return False

    try:
        os.remove(download_filename)
        os.remove(download_filename + ".tif")
        os.remove(download_filename + "_unscaled.tif")
    except:
        log(f"× Could not delete a temp file ({download_filename}).",
            "WARN", indentLevel=2, remote=True, model=model_name)

    try:
        pg.ConnectionPool.curr.execute("DELETE FROM eolus3." +
                                       table_name + " WHERE fh = %s", (fh,))
        pg.ConnectionPool.conn.commit()
    except:
        pg.reset()
        log("Couldn't update the DB that this band was processed.",
            "ERROR", indentLevel=2, remote=True, model=model_name)
        return False

    return True


def process(model_name, table_name, full_fh, timestamp, band):
    model = models[model_name]
    processed = False

    band_str = ""
    if band:
        band_str = " AND grib_var = '" + band["shorthand"] + "'"

    try:
        pg.ConnectionPool.curr.execute("SELECT band FROM eolus3." + table_name +
                                       " WHERE fh = '" + full_fh + "' " + band_str)
        band_number = pg.ConnectionPool.curr.fetchone()[0]
    except:
        pg.reset()
        log("× Some other agent finished the model.", "NOTICE",
            indentLevel=1, remote=True, model=model_name)
        return False

    fileExists = model_tools.check_if_model_fh_available(
        model_name, timestamp, full_fh)

    if fileExists:
        log("· Start processing fh " + full_fh + ".", "INFO",
            remote=True, model=model_name, indentLevel=1)
        if band is None:
            try:
                success = download_full_file(
                    model_name, timestamp, full_fh, table_name)
                if not success:
                    return False
            except:
                return False
        else:
            try:
                success = download_band(
                    model_name, timestamp, full_fh, band, table_name)
                if not success:
                    return False
            except:
                return False

        processed = True

    # delete the table if all steps are done
    try:
        pg.ConnectionPool.curr.execute("SELECT COUNT(*) FROM eolus3." +
                                       table_name + " WHERE status != 'DONE'")
        num_bandsRemaining = pg.ConnectionPool.curr.fetchone()[0]
    except:
        pg.reset()
        log("Couldn't get remaining count from table " + table_name +
            ".", "ERROR", indentLevel=1, remote=True, model=model_name)
        return False

    noun = "bands"
    if band is None:
        noun = "forecast hours"

    log("· There are " + str(num_bandsRemaining) + " remaining " +
        noun + " to process.", "DEBUG", indentLevel=1)

    if num_bandsRemaining == 0:
        log("· Deleting table " + table_name + ".", "NOTICE",
            indentLevel=1, remote=True, model=model_name)
        try:
            pg.ConnectionPool.curr.execute("DROP TABLE eolus3." + table_name)
            pg.ConnectionPool.conn.commit()
        except:
            pg.reset()
            log("Couldn't remove the table " + table_name + ".",
                "ERROR", indentLevel=1, remote=True, model=model_name)
            return False

        end(model_name)

    return processed


def end(model_name):

    file_tools.clean()

    try:
        log("✓ This model is completely finished processing.",
            "INFO", remote=True, model=model_name)
        pg.ConnectionPool.curr.execute(
            "UPDATE eolus3.models SET status = %s WHERE model = %s", ("WAITING", model_name))
        pg.ConnectionPool.conn.commit()
        update_run_status(model_name)
    except:
        pg.reset()
        log("Couldn't mark model as complete.",
            "ERROR", remote=True, model=model_name)
