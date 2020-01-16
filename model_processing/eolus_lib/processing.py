from eolus_lib.config import config
from eolus_lib.logger import log
import eolus_lib.pg_connection_manager as pg

def start_processing_model(model_name, timestamp):

    model = models[model_name]
    formatted_timestamp = timestamp.strftime('%Y%m%d_%HZ')

    log(f"· Started processing {model_name} | {formatted_timestamp} -- making table(s).",
        "INFO", indentLevel=1, remote=True, model=model_name)

    try:
        pg.ConnectionPool.curr.execute("UPDATE eolus3.models SET (status, timestamp) = (%s, %s) WHERE model = %s",
                     ("MAKINGTABLE", timestamp, model_name))
        pg.ConnectionPool.conn.commit()
    except:
        pg.reset()
        killScript(1)

    modelBandArray = makeModelBandArray(model_name)
    tableName = model_name + "_" + formatted_timestamp

    createBandTable(model_name, tableName)

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


def createBandTable(modelName, tableName):
    log(f"· Creating table | {tableName}", "NOTICE",
        indentLevel=1, remote=True, model=modelName)
    try:
        model = models[modelName]
        pg.ConnectionPool.curr.execute("CREATE TABLE eolus3." + tableName +
                     " (fh text, status text, band integer, start_time timestamp with time zone, grib_var text, agent text) WITH ( OIDS = FALSE )")
        pg.ConnectionPool.conn.commit()

    except:
        pg.reset()
        log("Could not create table. This will probably need to be manually fixed.",
            "ERROR", remote=True)
        return

    fh = model["startTime"]
    i = 1

    populated = False

    bands = makeModelBandArray(modelName)
    try:
        while not populated:
            fullFh = getFullFh(modelName, fh)
            if bands == None or len(bands) == 0:
                pg.ConnectionPool.curr.execute("INSERT INTO eolus3." + tableName +
                             " (fh, status, band) VALUES (%s, %s, %s)", (fullFh, "WAITING", str(i)))
                pg.ConnectionPool.conn.commit()
            else:
                for band in bands:
                    pg.ConnectionPool.curr.execute("INSERT INTO eolus3." + tableName + " (fh, status, band, grib_var) VALUES (%s, %s, %s, %s)",
                                 (fullFh, "WAITING", str(i), band["shorthand"]))
                    pg.ConnectionPool.conn.commit()
            fh = addAppropriateFhStep(modelName, fh)
            i += 1

            if fh > model["endTime"]:
                return
    except:
        pg.reset()
        log("An error ocpg.ConnectionPool.curred while making the table (" +
            tableName + ").", "ERROR", remote=True, model=modelName)
        return


def findModelStepToProcess(modelName):
    found = False
    model = models[modelName]
    fh = model["startTime"]
    origBand = -1

    try:
        pg.ConnectionPool.curr.execute(
            "SELECT timestamp FROM eolus3.models WHERE model = %s", (modelName,))
        timestamp = pg.ConnectionPool.curr.fetchone()[0]

        formattedTimestamp = timestamp.strftime('%Y%m%d_%HZ')
        tableName = modelName + "_" + formattedTimestamp

    except:
        pg.reset()
        log("Couldn't get the timetamp for model " +
            modelName, "ERROR", remote=True)

    try:
        pg.ConnectionPool.curr.execute("SELECT fh, grib_var, band FROM eolus3." + tableName +
                     " WHERE status = 'WAITING' ORDER BY band ASC LIMIT 1")
        res = pg.ConnectionPool.curr.fetchone()
        if not res or len(res) == 0:
            return False
        fullFh = res[0]
        gribVar = res[1]
        origBand = res[2]

    except:
        pg.reset()
        log("Couldn't get the status of a timestep from " +
            tableName, "ERROR", remote=True)
        return False

    band = None

    if not gribVar:
        band = None
    else:
        modelBandArray = makeModelBandArray(modelName)
        for bandItem in modelBandArray:
            if bandItem["shorthand"] == gribVar:
                band = bandItem
                break

    bandStr = ""
    if band:
        bandStr = " AND grib_var = '" + band["shorthand"] + "'"

    bandInfoStr = ""
    if band is not None:
        bandInfoStr = " | Band: " + band["shorthand"]

    try:
        pg.ConnectionPool.curr.execute("UPDATE eolus3." + tableName + " SET (status, start_time, agent) = (%s, %s, %s) WHERE fh = %s" +
                     bandStr, ("PROCESSING", datetime.utcnow(), pid, fullFh))
        pg.ConnectionPool.conn.commit()
    except:
        pg.reset()
        log("Couldn't set a status to processing in " +
            tableName, "ERROR", remote=True)

    log("· Attempting to process fh " + fullFh + bandInfoStr,
        "INFO", remote=True, indentLevel=1, model=modelName)
    processed = processModelStep(modelName, tableName, fullFh, timestamp, band)

    if processed:
        log("✓ Done.", "INFO", remote=True, indentLevel=1, model=modelName)
        return True

    else:
        try:
            log("· Setting back to waiting.", "INFO",
                remote=True, indentLevel=1, model=modelName)
            if gribVar is not None:
                pg.ConnectionPool.curr.execute("SELECT * FROM eolus3." + tableName +
                             " WHERE fh = '" + fullFh + "' AND grib_var = '" + gribVar + "'")
            else:
                pg.ConnectionPool.curr.execute("SELECT * FROM eolus3." +
                             tableName + " WHERE fh = '" + fullFh + "'")
            res = pg.ConnectionPool.curr.fetchone()

            if not res or len(res) == 0:
                pg.ConnectionPool.curr.execute("INSERT INTO eolus3." + tableName +
                             " (fh, status, band, grib_var) VALUES (%s,%s,%s,%s)", (fullFh, "WAITING", origBand, gribVar))
                pg.ConnectionPool.conn.commit()

            else:
                pg.ConnectionPool.curr.execute("UPDATE eolus3." + tableName + " SET (status, start_time) = (%s, %s) WHERE fh = %s" +
                             bandStr, ("WAITING", datetime.utcnow(), fullFh))
                pg.ConnectionPool.conn.commit()
        except Exception as e:
            pg.reset()
            log("Couldn't set a status to back to waiting in " + tableName +
                "... This will need manual intervention.", "ERROR", remote=True)
            log(repr(e), "ERROR", indentLevel=2, remote=True, model=modelName)
        return False


def downloadBand(modelName, timestamp, fh, band, tableName):
    model = models[modelName]

    try:
        pg.ConnectionPool.curr.execute("SELECT band FROM eolus3." +
                     tableName + " WHERE fh = %s", (fh,))
        bandNumber = pg.ConnectionPool.curr.fetchone()[0]
    except:
        pg.reset()
        log("Couldn't get the next band to process, fh " + fh + ", table " +
            tableName, "ERROR", remote=True, indentLevel=2, model=modelName)
        return False

    url = makeUrl(modelName, timestamp.strftime(
        "%Y%m%d"), timestamp.strftime("%H"), fh)

    fileName = getBaseFileName(modelName, timestamp, band)
    targetDir = config["mapfileDir"] + "/" + modelName + "/"
    targetRawDir = config["mapfileDir"] + "/rawdata/" + modelName + "/"
    downloadFileName = config["tempDir"] + "/" + \
        fileName + "_t" + fh + "." + model["filetype"]
    targetFileName = targetDir + fileName + ".tif"
    targetRawFileName = targetRawDir + fileName + ".tif"

    try:
        response = requests.head(url)
        if response.status_code != 200 or response.status_code == None or response == None:
            log(f"· This index file is not ready yet. " + url,
                "WARN", remote=True, indentLevel=2, model=modelName)
            return False

        contentLength = str(response.headers["Content-Length"])
    except:
        log(f"· Couldn't get header of " + url, "ERROR",
            remote=True, indentLevel=2, model=modelName)
        return False

    byteRange = getByteRange(band, url + ".idx", contentLength)

    if not byteRange or byteRange == None:
        log(f"· Band {band['shorthand']} doesn't exist for fh {fh}.",
            "WARN", remote=True, indentLevel=2, model=modelName)
        try:
            pg.ConnectionPool.curr.execute("DELETE FROM eolus3." + tableName +
                         " WHERE fh = %s AND grib_var = %s", (fh, band["shorthand"]))
            pg.ConnectionPool.conn.commit()
        except:
            pg.reset()
            log("Couldn't delete an unusable band from the table. " + fh + ", table " +
                tableName, "ERROR", remote=True, indentLevel=2, model=modelName)
        return True

    log(f"↓ Downloading band {band['shorthand']} for fh {fh}.",
        "NOTICE", indentLevel=2, remote=True, model=modelName)
    try:
        response = http.request('GET', url,
                                headers={
                                    'Range': 'bytes=' + byteRange
                                },
                                retries=5)

        f = open(downloadFileName, 'wb')
        f.write(response.data)
        f.close()
    except:
        log("Couldn't read the band -- the request likely timed out. " + fh +
            ", table " + tableName, "ERROR", indentLevel=2, remote=True, model=modelName)
        return False

    log(f"✓ Downloaded band {band['shorthand']} for fh {fh}.",
        "NOTICE", indentLevel=2, remote=True, model=modelName)

    bounds = config["bounds"][model["bounds"]]
    width = model["imageWidth"]

    epsg4326 = osr.SpatialReference()
    epsg4326.ImportFromEPSG(4326)

    log("· Warping downloaded data.", "NOTICE",
        indentLevel=2, remote=True, model=modelName)
    try:
        gribFile = gdal.Open(downloadFileName)
        outFile = gdal.Warp(
            downloadFileName + ".tif",
            gribFile,
            format='GTiff',
            outputBounds=[bounds["left"], bounds["bottom"],
                          bounds["right"], bounds["top"]],
            dstSRS=epsg4326,
            width=width,
            resampleAlg=gdal.GRA_CubicSpline)
        outFile.FlushCache()
        outFile = None

        outFile = gdal.Warp(
            downloadFileName + "_unscaled.tif",
            gribFile,
            format='GTiff',
            outputBounds=[bounds["left"], bounds["bottom"],
                          bounds["right"], bounds["top"]],
            dstSRS=epsg4326,
            creationOptions=["COMPRESS=deflate", "ZLEVEL=9"],
            resampleAlg=gdal.GRA_CubicSpline)
        outFile.FlushCache()
        outFile = None

        gribFile = None
    except Exception as e:
        log("Warping failed -- " + downloadFileName, "ERROR", remote=True)
        log(repr(e), "ERROR", indentLevel=2, remote=True, model=modelName)
        return False

    # check to see if the working raster exists
    if not os.path.exists(targetFileName):
        log(f"· Creating output master TIF | {targetFileName}",
            "NOTICE", indentLevel=2, remote=True, model=modelName)
        try:
            os.makedirs(targetDir)
        except:
            log("· Directory already exists.", "INFO",
                indentLevel=2, remote=False, model=modelName)

        numBands = getNumberOfHours(modelName)

        try:
            gribFile = gdal.Open(downloadFileName + ".tif")
            geoTransform = gribFile.GetGeoTransform()
            width = gribFile.RasterXSize
            height = gribFile.RasterYSize

            newRaster = gdal.GetDriverByName('MEM').Create(
                '', width, height, numBands, gdal.GDT_Float32)
            newRaster.SetProjection(gribFile.GetProjection())
            newRaster.SetGeoTransform(list(geoTransform))
            gdal.GetDriverByName('GTiff').CreateCopy(
                targetFileName, newRaster, 0)
            log("✓ Output master TIF created.", "NOTICE",
                indentLevel=2, remote=True, model=modelName)
        except Exception as e:
            log("Couldn't create the new TIF: " + targetFileName,
                "ERROR", indentLevel=2, remote=True, model=modelName)
            log(repr(e), "ERROR", indentLevel=2, remote=True, model=modelName)
            return False

    # check to see if the working raster exists
    if not os.path.exists(targetRawFileName):
        log(f"· Creating output master TIF | {targetRawFileName}",
            "NOTICE", indentLevel=2, remote=True, model=modelName)
        try:
            os.makedirs(targetRawDir)
        except:
            log("· Directory already exists.", "INFO",
                indentLevel=2, remote=False, model=modelName)

        numBands = getNumberOfHours(modelName)

        try:
            gribFile = gdal.Open(downloadFileName + "_unscaled.tif")
            geoTransform = gribFile.GetGeoTransform()
            width = gribFile.RasterXSize
            height = gribFile.RasterYSize

            newRaster = gdal.GetDriverByName('MEM').Create(
                '', width, height, numBands, gdal.GDT_Float32)
            newRaster.SetProjection(gribFile.GetProjection())
            newRaster.SetGeoTransform(list(geoTransform))
            gdal.GetDriverByName('GTiff').CreateCopy(
                targetRawFileName, newRaster, 0)
            log("✓ Output master TIF created.", "NOTICE",
                indentLevel=2, remote=True, model=modelName)
        except Exception as e:
            log("Couldn't create the new TIF: " + targetRawFileName,
                "ERROR", indentLevel=2, remote=True, model=modelName)
            log(repr(e), "ERROR", indentLevel=2, remote=True, model=modelName)
            return False

    log(f"· Writing data to the GTiff | band: {band['shorthand']} | fh: {fh} | bandNumber: {str(bandNumber)}",
        "NOTICE", indentLevel=2, remote=True, model=modelName)

    try:
        # Copy the downloaded band to this temp file
        gribFile = gdal.Open(downloadFileName + ".tif")
        data = gribFile.GetRasterBand(1).ReadAsArray()

        tif = gdal.Open(targetFileName, gdalconst.GA_Update)
        tif.GetRasterBand(bandNumber).WriteArray(data)
        tif.FlushCache()

        gribFile = gdal.Open(downloadFileName + "_unscaled.tif")
        data = gribFile.GetRasterBand(1).ReadAsArray()

        tif = gdal.Open(targetRawFileName, gdalconst.GA_Update)
        tif.GetRasterBand(bandNumber).WriteArray(data)
        tif.FlushCache()

        gribFile = None
        tif = None
        log(f"✓ Data written to the GTiff | band: {band['shorthand']} | fh: {fh}.",
            "NOTICE", indentLevel=2, remote=True, model=modelName)
    except Exception as e:
        log(f"Couldn't write band to TIF | band: {band['shorthand']} | fh: {fh}.",
            "ERROR", indentLevel=2, remote=True, model=modelName)
        log(repr(e), "ERROR", indentLevel=2, remote=True, model=modelName)
        return False

    try:
        os.remove(downloadFileName)
        os.remove(downloadFileName + ".tif")
        os.remove(downloadFileName + "_unscaled.tif")
    except:
        log(f"× Could not delete a temp file ({downloadFileName}).",
            "WARN", indentLevel=2, remote=True, model=modelName)

    try:
        pg.ConnectionPool.curr.execute("DELETE FROM eolus3." + tableName +
                     " WHERE fh = %s AND grib_var = %s", (fh, band["shorthand"]))
        pg.ConnectionPool.conn.commit()
    except:
        pg.reset()
        log("Couldn't update the DB that this band was processed.",
            "ERROR", indentLevel=2, remote=True, model=modelName)
        return False

    return True


'''
    Copied a bit from https://github.com/cacraig/grib-inventory/ - thanks!
'''


def getByteRange(band, idxFile, contentLength):
    log(f"· Searching for band defs in index file {idxFile}",
        "DEBUG", indentLevel=2, remote=True)
    try:
        response = http.request('GET', idxFile)
        data = response.data.decode('utf-8')
        varNameToFind = band["band"]["var"]
        levelToFind = getLevelNameForLevel(band["band"]["level"], "idxName")
        found = False
        startByte = None
        endByte = None

        for line in data.splitlines():
            line = str(line)
            parts = line.split(':')
            varName = parts[3]
            level = parts[4]
            time = parts[5]

            if found:
                endByte = parts[1]
                break

            if varName == varNameToFind and level == levelToFind:
                if "timeRange" in band["band"].keys():
                    rangeVal = time.split(" ", 1)[0]
                    ranges = rangeVal.split("-")
                    if (int(ranges[1]) - int(ranges[0])) != band["band"]["timeRange"]:
                        continue

                log("✓ Found.", "DEBUG", indentLevel=2, remote=False)
                found = True
                startByte = parts[1]
                continue

        if found:
            if endByte == None:
                endByte = contentLength

            log(f"· Bytes {startByte} to {endByte}", "DEBUG", indentLevel=2)
            if startByte == endByte:
                return None

            return startByte + "-" + endByte
        else:
            log(f"· Couldn't find band def in index file.",
                "WARN", indentLevel=2, remote=True)
        return None

    except:
        log(f"Band def retrieval failed.", "ERROR", indentLevel=2, remote=True)
        return None


def downloadFullFile(modelName, timestamp, fh, tableName):
    model = models[modelName]
    try:
        pg.ConnectionPool.curr.execute("SELECT band FROM eolus3." +
                     tableName + " WHERE fh = %s", (fh,))
        bandNumber = pg.ConnectionPool.curr.fetchone()[0]
    except:
        pg.reset()
        log("Couldn't get the next fh to process, fh " + fh + ", table " +
            tableName, "ERROR", remote=True, indentLevel=2, model=modelName)
        return False

    url = makeUrl(modelName, timestamp.strftime(
        "%Y%m%d"), timestamp.strftime("%H"), fh)

    fileName = getBaseFileName(modelName, timestamp, None)
    targetDir = config["mapfileDir"] + "/" + modelName + "/"
    targetRawDir = config["mapfileDir"] + "/rawdata/" + modelName + "/"
    downloadFileName = config["tempDir"] + "/" + \
        fileName + "_t" + fh + "." + model["filetype"]

    try:
        os.makedirs(targetDir)
    except:
        log("· Directory already exists.", "INFO",
            indentLevel=2, remote=False, model=modelName)

    try:
        os.makedirs(targetRawDir)
    except:
        log("· Directory already exists.", "INFO",
            indentLevel=2, remote=False, model=modelName)

    log(f"↓ Downloading fh {fh}.", "NOTICE",
        indentLevel=2, remote=True, model=modelName)
    try:
        response = http.request('GET', url, retries=5)

        f = open(downloadFileName, 'wb')
        f.write(response.data)
        f.close()
        log(f"✓ Downloaded band fh {fh}.", "NOTICE",
            indentLevel=2, remote=True, model=modelName)
    except:
        log("Couldn't read the fh -- the request likely timed out. " + fh +
            ", table " + tableName, "ERROR", indentLevel=2, remote=True, model=modelName)
        return False

    bounds = config["bounds"][model["bounds"]]
    width = model["imageWidth"]

    try:
        epsg4326 = osr.SpatialReference()
        epsg4326.ImportFromEPSG(4326)

        log("· Warping downloaded data.", "NOTICE",
            indentLevel=2, remote=True, model=modelName)
        try:
            os.remove(downloadFileName + ".tif")
        except:
            log("· No old file to remove.", "DEBUG", indentLevel=2)

        gribFile = gdal.Open(downloadFileName)
        outFile = gdal.Warp(
            downloadFileName + ".tif",
            gribFile,
            format='GTiff',
            outputBounds=[bounds["left"], bounds["bottom"],
                          bounds["right"], bounds["top"]],
            dstSRS=epsg4326,
            width=width,
            resampleAlg=gdal.GRA_CubicSpline)
        outFile.FlushCache()

        outFile = gdal.Warp(
            downloadFileName + "_unscaled.tif",
            gribFile,
            format='GTiff',
            outputBounds=[bounds["left"], bounds["bottom"],
                          bounds["right"], bounds["top"]],
            dstSRS=epsg4326,
            creationOptions=["COMPRESS=deflate", "ZLEVEL=9"],
            resampleAlg=gdal.GRA_CubicSpline)
        outFile.FlushCache()

        outFile = None
        gribFile = None

    except:
        log("Warping failed -- " + downloadFileName, "ERROR",
            indentLevel=2, remote=True, model=modelName)
        return False

    numBands = getNumberOfHours(modelName)

    bands = makeModelBandArray(modelName, force=True)
    if bands == None:
        try:
            os.makedirs(targetDir)
        except:
            log("· Directory already exists.", "INFO",
                indentLevel=2, remote=True, model=modelName)

        try:
            os.makedirs(targetRawDir)
        except:
            log("· Directory already exists.", "INFO",
                indentLevel=2, remote=False, model=modelName)

        targetFileName = targetDir + \
            getBaseFileName(modelName, timestamp, None) + "_t" + fh + ".tif"
        targetRawFileName = targetRawDir + \
            getBaseFileName(modelName, timestamp, None) + "_t" + fh + ".tif"
        log("· Copying to " + targetFileName, "NOTICE",
            indentLevel=2, remote=True, model=modelName)

        try:
            shutil.copyfile(downloadFileName + ".tif", targetFileName)
            shutil.copyfile(downloadFileName +
                            "_unscaled.tif", targetRawFileName)
        except:
            log("Couldn't copy.", "ERROR", indentLevel=2,
                remote=True, model=modelName)
            return False

    else:
        log(f"· Extracting bands for fh {fh}.", "INFO",
            indentLevel=2, remote=True, model=modelName)

        for band in bands:
            targetFileName = targetDir + \
                getBaseFileName(modelName, timestamp, band) + ".tif"
            targetRawFileName = targetRawDir + \
                getBaseFileName(modelName, timestamp, band) + ".tif"
            if not os.path.exists(targetFileName):
                log(f"· Creating output master TIF with {str(numBands) } bands | {targetFileName}",
                    "NOTICE", indentLevel=2, remote=True, model=modelName)
                try:
                    os.makedirs(targetDir)
                except:
                    log("· Directory already exists.", "INFO",
                        indentLevel=2, remote=True, model=modelName)

                try:
                    gribFile = gdal.Open(downloadFileName + ".tif")
                    geoTransform = gribFile.GetGeoTransform()
                    width = gribFile.RasterXSize
                    height = gribFile.RasterYSize

                    newRaster = gdal.GetDriverByName('MEM').Create(
                        '', width, height, numBands, gdal.GDT_Float32)
                    newRaster.SetProjection(gribFile.GetProjection())
                    newRaster.SetGeoTransform(list(geoTransform))
                    gdal.GetDriverByName('GTiff').CreateCopy(
                        targetFileName, newRaster, 0)
                    gribFile = None
                    newRaster = None
                    log("✓ Output master TIF created.", "NOTICE",
                        indentLevel=2, remote=True, model=modelName)
                except:
                    log("Couldn't create the new TIF.", "ERROR",
                        indentLevel=2, remote=True, model=modelName)
                    return False

            if not os.path.exists(targetRawFileName):
                log(f"· Creating output master TIF with {str(numBands) } bands | {targetRawFileName}",
                    "NOTICE", indentLevel=2, remote=True, model=modelName)
                try:
                    os.makedirs(targetRawDir)
                except:
                    log("· Directory already exists.", "INFO",
                        indentLevel=2, remote=False, model=modelName)

                try:
                    gribFile = gdal.Open(downloadFileName + "_unscaled.tif")
                    geoTransform = gribFile.GetGeoTransform()
                    width = gribFile.RasterXSize
                    height = gribFile.RasterYSize

                    newRaster = gdal.GetDriverByName('MEM').Create(
                        '', width, height, numBands, gdal.GDT_Float32)
                    newRaster.SetProjection(gribFile.GetProjection())
                    newRaster.SetGeoTransform(list(geoTransform))
                    gdal.GetDriverByName('GTiff').CreateCopy(
                        targetRawFileName, newRaster, 0)
                    gribFile = None
                    newRaster = None
                    log("✓ Output master TIF created.", "NOTICE",
                        indentLevel=2, remote=True, model=modelName)
                except:
                    log("Couldn't create the new TIF.", "ERROR",
                        indentLevel=2, remote=True, model=modelName)
                    return False

            log(f"· Writing data to the GTiff | band: {band['shorthand']} | fh: {fh}",
                "NOTICE", indentLevel=2, remote=True, model=modelName)
            # Copy the downloaded band to this temp file
            try:
                gribFile = gdal.Open(downloadFileName + ".tif")
                gribNumBands = gribFile.RasterCount
                bandLevel = getLevelNameForLevel(
                    band["band"]["level"], "gribName")
                tif = gdal.Open(targetFileName, gdalconst.GA_Update)
                for i in range(1, gribNumBands + 1):
                    try:
                        fileBand = gribFile.GetRasterBand(i)
                        metadata = fileBand.GetMetadata()
                        if metadata["GRIB_ELEMENT"].lower() == band["band"]["var"].lower() and metadata["GRIB_SHORT_NAME"].lower() == bandLevel.lower():
                            log("· Band " + band["band"]["var"] + " found.",
                                "DEBUG", indentLevel=2, remote=False)
                            data = fileBand.ReadAsArray()
                            tif.GetRasterBand(bandNumber).WriteArray(data)
                            break

                    except:
                        log(f"× Couldn't read GTiff band: #{str(i)} | fh: {fh}",
                            "WARN", indentLevel=2, remote=True, model=modelName)

                tif.FlushCache()

                gribFile = gdal.Open(downloadFileName + "_unscaled.tif")
                tif = gdal.Open(targetRawFileName, gdalconst.GA_Update)
                for i in range(1, gribNumBands + 1):
                    try:
                        fileBand = gribFile.GetRasterBand(i)
                        metadata = fileBand.GetMetadata()
                        if metadata["GRIB_ELEMENT"].lower() == band["band"]["var"].lower() and metadata["GRIB_SHORT_NAME"].lower() == bandLevel.lower():
                            log("· Band " + band["band"]["var"] + " found.",
                                "DEBUG", indentLevel=2, remote=False)
                            data = fileBand.ReadAsArray()
                            tif.GetRasterBand(bandNumber).WriteArray(data)
                            break

                    except:
                        log(f"× Couldn't read GTiff band: #{str(i)} | fh: {fh}",
                            "WARN", indentLevel=2, remote=True, model=modelName)

                tif.FlushCache()
                gribFile = None
                tif = None
            except Exception as e:
                log("Couldn't write bands to the tiff. " + fh + ", table " +
                    tableName, "ERROR", indentLevel=2, remote=True, model=modelName)
                log(repr(e), "ERROR", indentLevel=2,
                    remote=True, model=modelName)
                return False

    try:
        os.remove(downloadFileName)
        os.remove(downloadFileName + ".tif")
        os.remove(downloadFileName + "_unscaled.tif")
    except:
        log(f"× Could not delete a temp file ({downloadFileName}).",
            "WARN", indentLevel=2, remote=True, model=modelName)

    try:
        pg.ConnectionPool.curr.execute("DELETE FROM eolus3." +
                     tableName + " WHERE fh = %s", (fh,))
        pg.ConnectionPool.conn.commit()
    except:
        pg.reset()
        log("Couldn't update the DB that this band was processed.",
            "ERROR", indentLevel=2, remote=True, model=modelName)
        return False

    return True


def processModelStep(modelName, tableName, fullFh, timestamp, band):
    model = models[modelName]
    processed = False

    bandStr = ""
    if band:
        bandStr = " AND grib_var = '" + band["shorthand"] + "'"

    try:
        pg.ConnectionPool.curr.execute("SELECT band FROM eolus3." + tableName +
                     " WHERE fh = '" + fullFh + "' " + bandStr)
        bandNumber = pg.ConnectionPool.curr.fetchone()[0]
    except:
        pg.reset()
        log("× Some other agent finished the model.", "NOTICE",
            indentLevel=1, remote=True, model=modelName)
        killScript(0)

    fileExists = checkIfModelFhAvailable(modelName, timestamp, fullFh)

    if fileExists:
        log("· Start processing fh " + fullFh + ".", "INFO",
            remote=True, model=modelName, indentLevel=1)
        if band is None:
            try:
                success = downloadFullFile(
                    modelName, timestamp, fullFh, tableName)
                if not success:
                    return False
            except:
                return False
        else:
            try:
                success = downloadBand(
                    modelName, timestamp, fullFh, band, tableName)
                if not success:
                    return False
            except:
                return False

        processed = True

    #delete the table if all steps are done
    try:
        pg.ConnectionPool.curr.execute("SELECT COUNT(*) FROM eolus3." +
                     tableName + " WHERE status != 'DONE'")
        numBandsRemaining = pg.ConnectionPool.curr.fetchone()[0]
    except:
        pg.reset()
        log("Couldn't get remaining count from table " + tableName +
            ".", "ERROR", indentLevel=1, remote=True, model=modelName)
        killScript(1)

    noun = "bands"
    if band is None:
        noun = "forecast hours"

    log("· There are " + str(numBandsRemaining) + " remaining " +
        noun + " to process.", "DEBUG", indentLevel=1)

    if numBandsRemaining == 0:
        log("· Deleting table " + tableName + ".", "NOTICE",
            indentLevel=1, remote=True, model=modelName)
        try:
            pg.ConnectionPool.curr.execute("DROP TABLE eolus3." + tableName)
            pg.ConnectionPool.conn.commit()
        except:
            pg.reset()
            log("Couldn't remove the table " + tableName + ".",
                "ERROR", indentLevel=1, remote=True, model=modelName)
            killScript(1)

        endModelProcessing(modelName)

    # If success, return True
    return processed


def makeModelBandArray(modelName, force=False):
    model = models[modelName]
    if not "bands" in model.keys():
        return None

    modelBandArray = []
    if model["index"] or force:
        for band in model["bands"]:
            modelBandArray.append({
                "shorthand": band["var"].lower() + "_" + band["level"].lower(),
                "band": band
            })

    return modelBandArray
