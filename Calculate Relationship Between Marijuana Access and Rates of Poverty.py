## Analyzing the spatial relationship between marijuana access and poverty in LA County
## By Lance Paul Sunga
## GEOG 50.03: GIS Programming and Database

import arcpy
import os
from scipy import stats

arcpy.env.workspace = r"D:\CLASSES\GEOG_50_03\LanceSunga\ClassProject\Marijuana_Accessibility_LA_2024"

arcpy.env.overwriteOutput = True

## Preparing files and workspaces

# Converting lyrxx files to shp files in Data folder
input_lyrx = r"D:\CLASSES\GEOG_50_03\LanceSunga\ClassProject\Data\Los Angeles County.lyrx"
output_folder = r"D:\CLASSES\GEOG_50_03\LanceSunga\ClassProject\Marijuana_Accessibility_LA_2024\Data_ClassProject"
arcpy.conversion.FeatureClassToShapefile([input_lyrx], output_folder)

input_lyrx = r"D:\CLASSES\GEOG_50_03\LanceSunga\ClassProject\Data\CT20FIP24CSA_Pop24_Pov24.lyrx" # Again for the other lyrx file
arcpy.conversion.FeatureClassToShapefile([input_lyrx], output_folder)

# Setting the projection of all layers within a file geodatabase
arcpy.env.workspace = r"Data_ClassProject" # to ensure that it reads the subfolder
all_feature_class = arcpy.ListFeatureClasses()
target_spatial_reference = arcpy.Describe(r"Data_ClassProject\CT20FIP24CSA_Pop24_Pov24.shp").spatialReference
gdb_path = r"D:\CLASSES\GEOG_50_03\LanceSunga\ClassProject\Marijuana_Accessibility_LA_2024\Marijuana_Accessibility_LA_2024.gdb"

for fc in all_feature_class:
    print(fc[:-4])
    output_feature_class = os.path.join(gdb_path, fc[:-4] +"_SP")
    arcpy.management.Project(in_dataset = fc, out_dataset = output_feature_class, out_coor_system = target_spatial_reference)

arcpy.env.workspace = r"D:\CLASSES\GEOG_50_03\LanceSunga\ClassProject\Marijuana_Accessibility_LA_2024\Marijuana_Accessibility_LA_2024.gdb" # resetting the workplace to include gdb

## Calculating density of dispensaries within each tract

dispensary = "Marij_Disp_LA_export_SP"
split_tracts = "CT20FIP24CSA_Pop24_Pov24_SP"
density_layer = "CT20FIP24CSA_MarijDensity"
arcpy.analysis.SummarizeWithin(split_tracts, dispensary, density_layer)
arcpy.management.AddField(density_layer,"Disp_Density","DOUBLE")
arcpy.management.CalculateField(density_layer, "Disp_Density", "density(!Point_Count!, !POP24_TOTA!)", "PYTHON3", 
"""
def density(count, pop):
    if pop is None or pop == 0:
        return 0
    else:
        return (count / pop)
"""
)


arcpy.management.JoinField(split_tracts, "CT20FIP24C", "CT20FIP24CSA_MarijDensity", "CT20FIP24C", ["Disp_Density"])

## Preparing LA Roads For Network Analysis

# Selecting roads that are drivable
raw_roads = r"Data_ClassProject\tl_2025_06037_roads.shp"
drivable_roads = "Drivable_Roads_LA"
select_clause = (
    "MTFCC = 'S1100' OR "
    "MTFCC = 'S1200' OR "
    "MTFCC = 'S1400' OR "
    "MTFCC = 'S1500' OR "
    "MTFCC = 'S1630' OR "
    "MTFCC = 'S1640' OR "
    "MTFCC = 'S1730' OR "
    "MTFCC = 'S1740' OR "
    "MTFCC = 'S1750' OR "
    "MTFCC = 'S1780'")
arcpy.analysis.Select(raw_roads, drivable_roads, select_clause)


# Assigning speed limits to each road
field_name = "Limit_mph" 
field_type = "Double"
expression = "getSpeedLimit(!MTFCC!)"
code_block = """
def getSpeedLimit(mtfcc):
    if mtfcc == 'S1100':
        return 65
    elif mtfcc == 'S1200':
        return 55
    elif mtfcc == 'S1500':
        return 15
    elif mtfcc == 'S1630':
        return 35
    elif mtfcc == 'S1640':
        return 25
    elif mtfcc == 'S1730':
        return 10
    elif mtfcc == 'S1740':
        return 20
    elif mtfcc == 'S1750':
        return 15
    elif mtfcc == 'S1780':
        return 10
    else:
        return 30
"""
arcpy.management.AddField(drivable_roads, field_name, field_type)
arcpy.management.CalculateField(drivable_roads, field_name, expression, "Python3", code_block)

# Measuring the length of each road
field_name = "Length" 
field_type = "Double"
arcpy.management.AddField(drivable_roads, field_name, field_type)
arcpy.management.CalculateField(drivable_roads, field_name, "!shape.length@MILES!", "Python3") 

# Calculating the drive time of each road
field_name = "Drive_Time" 
field_type = "Double"
expression = "(!Length!/!Limit_mph!) * 60"
arcpy.management.AddField(drivable_roads, field_name, field_type)
arcpy.management.CalculateField(drivable_roads, field_name, expression, "Python3")

## Building the network

arcpy.management.CreateFeatureDataset(arcpy.env.workspace, "LA_Network", target_spatial_reference)
arcpy.management.CopyFeatures("Drivable_Roads_LA_SP", r"LA_Network\Drivable_Roads_LA")

network_dataset = r"D:\CLASSES\GEOG_50_03\LanceSunga\ClassProject\Marijuana_Accessibility_LA_2024\Marijuana_Accessibility_LA_2024.gdb\LA_Network\Driving" 
# Due to coding issues, I had to manually create the network and cost with tools and drop down

print(arcpy.Exists(network_dataset))

## Creating Service Area Polygons

network_dataset = r"LA_Network\Driving"  
dispensary = "Marij_Disp_LA_export_SP"
split_tracts = "CT20FIP24CSA_Pop24_Pov24_SP"

population_field = "POP24_TOTA"
breaks = [10, 20, 30] 
supply_value = 1

sa_layer = arcpy.na.MakeServiceAreaAnalysisLayer(
    network_data_source=network_dataset,
    layer_name="Dispensaries_ServiceArea",
    travel_mode="New Travel Mode",
    travel_direction="FROM_FACILITIES",
    cutoffs=breaks,
    output_type="POLYGONS",
    geometry_at_overlaps="OVERLAP",
    geometry_at_cutoffs="RINGS",
).getOutput(0)

arcpy.na.AddLocations(sa_layer, 'Facilities', dispensary)
arcpy.na.Solve(sa_layer)

sublayer = arcpy.na.GetNAClassNames(sa_layer)
print(sublayer)
polygons_layer = sublayer["SAPolygons"]
arcpy.management.CopyFeatures(str(sa_layer) + "\\" + polygons_layer, "Dispensaries_ServiceArea_Polygons")

arcpy.management.AddField("Dispensaries_ServiceArea_Polygons", "Weight", "DOUBLE")
arcpy.management.CalculateField("Dispensaries_ServiceArea_Polygons","Weight", "1.0 if !ToBreak! <= 10 else 0.6 if !ToBreak! <= 20 else 0.3","PYTHON3")

service_areas = "Dispensaries_ServiceArea_Polygons"

# Mapping Service Area polygons - #.shp indicate that it is undissolved to save length of file names
service_area_10min = "ServiceArea_10min_LA.shp" 
select_clause = '"ToBreak" <= 10'
arcpy.analysis.Select(service_areas, service_area_10min, select_clause)
arcpy.management.Dissolve("ServiceArea_10min_LA.shp", "ServiceArea_10min_LA")
service_area_20min = "ServiceArea_20min_LA.shp" 
select_clause = '"ToBreak" <= 20'
arcpy.analysis.Select(service_areas, service_area_20min, select_clause)
arcpy.management.Dissolve("ServiceArea_20min_LA.shp", "ServiceArea_20min_LA")
service_area_30min = "ServiceArea_30min_LA.shp" 
select_clause = '"ToBreak" <= 30'
arcpy.analysis.Select(service_areas, service_area_30min, select_clause)
arcpy.management.Dissolve("ServiceArea_30min_LA.shp", "ServiceArea_30min_LA")

## Calculating Supply Ratio of Every Dispensary (Step 1 of 2SFCA)

# Apportioning population to fragmental polygon
intersect_output = "CT20FIP24CSA_Intersect"
arcpy.management.AddField(split_tracts, "SplitTractArea", "DOUBLE")
arcpy.management.CalculateField(split_tracts, "SplitTractArea","!shape.getarea!('PLANAR')", "PYTHON3")
arcpy.analysis.Intersect([split_tracts, service_areas], intersect_output)
arcpy.management.AddField(intersect_output, "PieceArea", "DOUBLE")
arcpy.management.CalculateField(intersect_output, "PieceArea", "!shape.area!","PYTHON3")
arcpy.management.AddField(intersect_output, "AreaWeight", "DOUBLE")
arcpy.management.CalculateField(intersect_output, "AreaWeight", "!PieceArea! / !SplitTractArea!", "PYTHON3")
arcpy.management.AddField(intersect_output, "WeightedPop", "DOUBLE")
arcpy.management.CalculateField(intersect_output, "WeightedPop", "!POP24_TOTA! * !AreaWeight!", "PYTHON3")

# Joining results to service area polygons
arcpy.analysis.Statistics(intersect_output, "Disp_ServiceArea_Pop", [["WeightedPop", "SUM"]], "FacilityID")
arcpy.management.AddField("Disp_ServiceArea_Pop", "SupplyRatio", "DOUBLE")
arcpy.management.CalculateField("Disp_ServiceArea_Pop", "SupplyRatio", "1 / !SUM_WeightedPop! if !SUM_WeightedPop! not in (None, 0) else 0", "PYTHON3")

arcpy.management.JoinField(service_areas, "FacilityID", "Disp_ServiceArea_Pop", "FacilityID", ["SupplyRatio"])

## Calculating Access Score of Each Tract  (Step 2 of 2SFCA)

# Calculating access score of each dispensary
arcpy.analysis.Intersect([split_tracts, service_areas], "CT20FIP24CSA_ServiceArea")
arcpy.management.AddField("CT20FIP24CSA_ServiceArea","AccessScore","DOUBLE")
arcpy.management.CalculateField("CT20FIP24CSA_ServiceArea", "AccessScore", "!SupplyRatio! * !Weight!", "PYTHON3")
arcpy.analysis.Statistics("CT20FIP24CSA_ServiceArea", "CT20FIP24CSA_MarijAccess", [["AccessScore", "SUM"]], "CT20FIP24C")

# Joining all access scores to each tract
arcpy.management.JoinField(split_tracts, "CT20FIP24C", "CT20FIP24CSA_MarijAccess", "CT20FIP24C", ["SUM_AccessScore"])

## Running t-test

low_pov = []
high_pov = []

with arcpy.da.SearchCursor(split_tracts, ["SUM_AccessScore", "PovGroup"]) as cursor:
    for access, group in cursor:
        if group == 0:
            low_pov.append(access)
        elif group == 1:
            high_pov.append(access)

t_stat, p_value = stats.ttest_ind(low_pov, high_pov, equal_var=False)

print("Low poverty tracts:", len(low_pov))
print("High poverty tracts:", len(high_pov))
print("Low poverty mean:", sum(low_pov)/len(low_pov))
print("High poverty mean:", sum(high_pov)/len(high_pov))
print("T-statistic:", t_stat)
print("P-value:", p_value)

## Running equity analysis 

split_tracts = "CT20FIP24CSA_Pop24_Pov24_SP"

arcpy.management.AddField(split_tracts, "PovGroup", "SHORT")
arcpy.management.CalculateField(split_tracts, "PovGroup", "1 if !POV24_PERC! >= 0.20 else 0", "PYTHON3")
arcpy.analysis.Statistics(split_tracts,"EquityGap_Table",[["SUM_AccessScore", "MEAN"]], "PovGroup")
low_access = None
high_access = None

with arcpy.da.SearchCursor("EquityGap_Table",
                           ["PovGroup","MEAN_SUM_AccessScore"]) as cursor:
    for row in cursor:
        if row[0] == 0:
            low_access = row[1]
        elif row[0] == 1:
            high_access = row[1]

equity_gap = low_access - high_access

print("Low Poverty Mean Access:", low_access)
print("High Poverty Mean Access:", high_access)
print("Equity Gap:", equity_gap)

# Mapping Equity Index

arcpy.management.AddField(split_tracts, "EquityIndex", "DOUBLE")
arcpy.management.CalculateField(split_tracts, "EquityIndex", "!SUM_AccessScore! - !POV24_PERC!", "PYTHON3")

## Running Hot Spot Analysis

# Checking Threshold Distance
arcpy.stats.IncrementalSpatialAutocorrelation(
    split_tracts, 
    "SUM_AccessScore",      
    10, 
    5000,               
    5000,                   
    "EUCLIDEAN",  
    "NO_STANDARDIZATION",  
    "IncSpatialAuto_Table" 
)

# Running function
arcpy.stats.HotSpots(
    "CT20FIP24CSA_Pop24_Pov24_SP",
    "SUM_AccessScore",
    "Access_HotSpots",
    "FIXED_DISTANCE_BAND",
    "EUCLIDEAN_DISTANCE",
    "NONE",
    "15000")

# Joining to inital layer
arcpy.management.JoinField("Access_HotSpots", "Source_ID", split_tracts, "UniqueID", ["POP24_TOTA"])

# Calculating total population in Hot Spots
total_pop = 0
hotspot_pop = 0
with arcpy.da.SearchCursor("Access_HotSpots", ["POP24_TOTA", "Gi_Bin"]) as cursor:
    for pop, binval in cursor:
        total_pop += pop
        
        # Hot spots are Gi_Bin > 0
        if binval > 0:
            hotspot_pop += pop

percent_hotspot = (hotspot_pop / total_pop) * 100

print("Total population:", total_pop)
print("Population in hot spots:", hotspot_pop)
print("Percent of population in hot spots:", percent_hotspot)

# Calculating population in poverty in Hot Spots
arcpy.management.JoinField("Access_HotSpots", "Source_ID", "CT20FIP24CSA_Pop24_Pov24_SP", "UniqueID", ["POV24_TOTA"])
poverty_total_hotspots = 0
poverty_total_all = 0

with arcpy.da.SearchCursor("Access_HotSpots", ["Gi_Bin", "POV24_TOTA"]) as cursor:
    for gi_bin, pov_pop in cursor:

        # total poverty population in study area
        poverty_total_all += pov_pop

        # check if tract is a hotspot
        if gi_bin in [1,2,3]:
            poverty_total_hotspots += pov_pop

print("Total population in poverty:", poverty_total_all)
print("Population in poverty in hotspot tracts:", poverty_total_hotspots)

percent = (poverty_total_hotspots / poverty_total_all) * 100
print("Percent of poverty population in hotspots:", percent)

## Running OLS regression

# Cleaning fields for OLS regression

arcpy.management.AddField("CT20FIP24CSA_Pop24_Pov24_SP", "UniqueID", "LONG")
arcpy.management.CalculateField("CT20FIP24CSA_Pop24_Pov24_SP", "UniqueID", "!OBJECTID!", "PYTHON3")
arcpy.management.CalculateField("CT20FIP24CSA_Pop24_Pov24_SP","SUM_AccessScore", "0 if !SUM_AccessScore! == None else !SUM_AccessScore!", "PYTHON3")
arcpy.management.CalculateField("CT20FIP24CSA_Pop24_Pov24_SP","Disp_Density", "0 if !Disp_Density! == None else !Disp_Density!", "PYTHON3")

# Running Function
arcpy.stats.OrdinaryLeastSquares(
    "CT20FIP24CSA_Pop24_Pov24_SP",   
    "UniqueID",                     
    "MarijAccess_Poverty_OLS",           
    "SUM_AccessScore",                  
    "POV24_PERC;POP24_Blac_Perc;POV24_Blac_Perc;POP24_TOTA")


# Checking Moran's I
arcpy.stats.SpatialAutocorrelation(
    "MarijAccess_Poverty_OLS",
    "Residual",
    "GENERATE_REPORT",
    "K_NEAREST_NEIGHBORS",
    "EUCLIDEAN_DISTANCE",
    "ROW",
    None,
    None,
    8)

## Running Geographically Weighted Regression

# Running Function
gwr_output = "GWR_MarijAccess"
arcpy.stats.GeographicallyWeightedRegression(
    "CT20FIP24CSA_Pop24_Pov24_SP",        
    "SUM_AccessScore",                    
    "POV24_PERC;POP24_BLAC_PERC;POV24_BLAC_PERC;POP24_TOTA",  
    gwr_output,                           
    "ADAPTIVE",                           
    "AICc",                               
    None,                                 
    100)

# Checking Moran's I
arcpy.stats.SpatialAutocorrelation(
    "GWR_MarijAccess",
    "Residual",
    "GENERATE_REPORT",
    "K_NEAREST_NEIGHBORS",
    "EUCLIDEAN_DISTANCE",
    "ROW",
    None,
    None,
    8)
