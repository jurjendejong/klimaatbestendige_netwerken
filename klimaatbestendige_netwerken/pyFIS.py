"""
Module to read geodata of the Fairway Information Services of Rijkswaterstaat (http://vaarweginformatie.nl).

https://github.com/jurjendejong/klimaatbestendige_netwerken/blob/master/klimaatbestendige_netwerken/pyFIS.py

Jurjen de Jong, Deltares, 24-9-2019
"""

import requests
import logging
from shapely import wkt
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import nearest_points
import geopandas as gpd
from pathlib import Path
import pandas as pd
import sqlite3

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.WARNING)


class pyFIS:
    count = 500  # Number of reponses per page. This is also the default maximum

    def __init__(self, url='https://www.vaarweginformatie.nl/wfswms/dataservice/1.3'):
        self.baseurl = url

        response_geogeneration = self._parse_request('geogeneration')
        self.geogeneration = str(response_geogeneration['GeoGeneration'])
        self.publication_date = str(response_geogeneration['PublicationDate'])

        logger.info(f"Geogeneration: {self.geogeneration} - {response_geogeneration['PublicationDate']}")

        self.service_coordinate_system = 'epsg:4326'
        self.export_coordinate_system = None  # Set to none to not convert. Otherwise: 'epsg:28992'

    def list_geotypes(self):
        """Returns list of all geotypes"""
        return self._parse_request('geotype')

    def list_relations(self, geotype):
        """
        Returns list of all relations for given geotype
        Note: Not all relations are explicitly specified
        """
        return self._parse_request([geotype, 'relations'])

    def list_objects(self, geotype):
        """
        Returns dataframe of all objects for given geotype
        """

        # Get list of objects from memory, or load if not accessed yet before
        if hasattr(self, geotype):
            return getattr(self, geotype)

        result = self._parse_request([self.geogeneration, geotype])

        # Store in memory
        setattr(self, geotype, result)

        return result

    def list_all_objects(self):
        """
        Load all objects of all geotypes
        """
        for geotype in self.list_geotypes():
            self.list_objects(geotype)

    def get_object(self, geotype, objectid):
        """
        Load all data of one object

        >> get_object('bridge', 2123)
        return: objectdetails

        """
        objectid = str(objectid)
        return self._parse_request([self.geogeneration, geotype, objectid])

    def get_object_subobjects(self, geotype, objectid, geotype2):
        """
        Load all data of one object

        >> get_object_subobjects('bridge', 1217, 'opening')
        return: [openingid#1, openingid#2, ...]

        """
        objectid = str(objectid)
        return self._parse_request([self.geogeneration, geotype, objectid, geotype2])

    def _parse_request(self, components):
        """
        Internal command to create and send requets of different kind. It combines
        components with the baseurl and reads the response. If the data contains
        'Result' it will be processed as a multi-page datasource and converted to DataFrame.
        """

        if not isinstance(components, list): components = [components]
        url = self.baseurl + '/' + '/'.join(components)

        logger.info('Reading: {}'.format(', '.join(components)))

        # Request loop
        result = []
        offset = 0

        while True:
            url_page = url + f'?offset={offset}&count={self.count}'
            logger.debug(f'Requesting: {url_page}')
            response = requests.get(url_page)
            assert response, f'An error has occured. URL: {url}. Response: {response}'

            response_dict = response.json()

            if 'Result' in response_dict:
                # Multi page response
                result.extend(response_dict['Result'])

                if response_dict['Offset'] + response_dict['Count'] < response_dict['TotalCount']:
                    # Go to next page
                    offset += self.count
                else:
                    # Arrived on the final page
                    result = gpd.GeoDataFrame(result)
                    break
            else:
                # Single page. Looping not required

                # When requesting single object, this should also be handles as a single multi-page response
                if 'Geometry' in response_dict:
                    result = gpd.GeoDataFrame([response_dict])
                else:
                    # Result is the dict itself
                    result = response_dict
                break

        # Process the requested data

        if 'Geometry' in result:
            # Convert data to real geometry data and transform to given coordinate system
            result.rename(axis=1, mapper={'Geometry': 'geometry'}, inplace=True)
            try:
                result['geometry'] = result['geometry'].apply(wkt.loads)
                if self.export_coordinate_system:
                    result.crs = {'init': self.service_coordinate_system}
                    result.to_crs({'init': self.export_coordinate_system})
            except:
                logger.warning('Could not convert geometry according to WKT format')
        return result

    def find_object_by_value(self, geotype, fieldvalue, fieldname='Name'):
        list_objects = self.list_objects(geotype)

        result = list_objects[list_objects[fieldname] == fieldvalue]
        return result

    def find_object_by_polygon(self, geotype, polygon):
        """
        Find all objects within given polygon
        Polygon may be of type tuple or shapely Polygon

        pol = [(5.774, 51.898),
               (5.742, 51.813),
               (6.020, 51.779),
               (5.951, 51.912),
               (5.774, 51.898),
               ]
        find_object_by_polygon('bridge', pol)
        """
        if not isinstance(polygon, Polygon) and \
           not isinstance(polygon, MultiPolygon):  # If type is not yet Polygon, make it a polygon
            polygon = Polygon(polygon)
        df = self.list_objects(geotype)
        df = df[df.geometry.within(polygon)]
        return df

    def find_closest_object(self, geotype, point):
        """
        Find object closest to given point
        Point may be of type tuple or shapely Point

        point = (5.774, 51.898)
        find_closest_object('bridge', point)

        """
        if not isinstance(point, Point):
            point = Point(point)

        df = self.list_objects(geotype)

        p, _ = nearest_points(df.unary_union, point)
        return df[df['geometry'] == p]

    def merge_geotypes(self, left_geotype, right_geotype, left_on=None,
                       right_on=None):
        """
        Load two geotypes and apply inner join.

        merge_geotypes('bridge', 'opening')

        """

        df_l = self.list_objects(left_geotype)
        df_r = self.list_objects(right_geotype)

        # If join fields are not set, they are assumed:
        if (not left_on) or (not right_on):
            if 'ParentGeoType' in df_r.columns:
                left_on = ['GeoType', 'Id']
                right_on = ['ParentGeoType', 'ParentId']
            else:
                left_on = ['Id']
                right_on = ['ParentId']

        df_merge = df_l.merge(df_r, left_on=left_on, right_on=right_on, suffixes=('', f'_{right_geotype}'))
        return df_merge

    def export(self, filepath, filetype=None, force=True, geotypes=None):
        """

        Export entire server to excel or sqlite database
        Used for backuping.

        filetype = [None, xlsx, xls, csv]
                if None, the filepath should end with filetype extension
        force = boleaan. Overwrite file if already exists
        geotypes = only export specific geotypes

        """
        # TODO: implement sqlite
        filepath = Path(filepath)
        if not filetype:
            filetype = filepath.suffix[1:]

        if filepath.exists():
            if not force:
                FileExistsError()
            else:
                filepath.unlink()

        if geotypes is None:
            geotypes = self.list_geotypes()

        if filetype in ['xlsx', 'xls']:
            logger.debug('Writing to excel')
            # Write to excel
            writer = pd.ExcelWriter(filepath, engine='xlsxwriter')

            for geotype in geotypes:
                logger.debug(f'Writing: {geotype}')
                df = self.list_objects(geotype)
                sheet_name = geotype[:31]
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            logger.debug(f'Saving excel')
            writer.save()
        elif filetype == 'csv':
            for geotype in geotypes:
                logger.debug(f'Writing: {geotype}')
                df = self.list_objects(geotype)
                filepath_geotype = (filepath.parent / f'{filepath.stem}_{geotype}.csv')
                df.to_csv(filepath_geotype, index=False)
        else:
            logger.error(f'Unrecognised filetype: {filetype}')
            NotImplementedError('Unrecognised filetype')


if __name__ == '__main__':
    # Some test calls
    FIS = pyFIS()
    FIS.list_geotypes()
    FIS.list_relations('lock')
    FIS.list_objects('chamber')

    FIS.merge_geotypes('bridge', 'opening')

    pol = [(5.774, 51.898),
           (5.742, 51.813),
           (6.020, 51.779),
           (5.951, 51.912),
           (5.774, 51.898),
           ]
    FIS.find_object_by_polygon('bridge', pol)
    FIS.find_closest_object('bridge', pol[0])
