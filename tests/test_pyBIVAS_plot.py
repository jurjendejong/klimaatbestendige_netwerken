from unittest import TestCase
from klimaatbestendige_netwerken.pyBIVAS_plot import pyBIVAS_plot as pyBIVAS
from klimaatbestendige_netwerken.pyBIVAS_plot import IVS90_analyse
from pathlib import Path

class TestpyBIVAS_plot(TestCase):

    skipSlowRuns = True
    # skipSlowRuns=("TRAVIS" in os.environ and os.environ["TRAVIS"] == "true")

    database_file = Path('resources/bivas_LSM_2018_NWMinput_lsm2bivas_v2018_02.db')

    def setUp(self):
        # Test if database exists
        if not self.database_file.exists():
            self.skipTest('Database could not be found')

        # Connect to database
        self.BIVAS = pyBIVAS(self.database_file)
        self.BIVAS.set_scenario(47)

        self.arcLabel = 'Waal'
        self.arcID = self.BIVAS.Arcs[self.arcLabel]

        self.BIVAS.outputdir = Path('export_pyBIVAS_plot')


    def test_plot_trips_arc(self):
        self.BIVAS.plot_Trips_Arc(arcID=self.arcID, label='test')

    def test_plot_vrachtanalyse(self):
        self.BIVAS.plot_Vrachtanalyse()

    def test_plot_vergelijking_vaarwegen(self):
        self.BIVAS.plot_vergelijking_vaarwegen()

    def test_plot_vergelijking_traffic_scenario(self):
        self.BIVAS.plot_vergelijking_trafficScenarios([13,14,12])

    def test_plot_beladingsgraad(self):
        self.BIVAS.plot_Beladingsgraad(self.arcID, self.arcLabel)

    def test_plot_vlootopbouw(self):
        self.BIVAS.plot_Vlootopbouw(self.arcID, self.arcLabel)


class Test_IVS90_analyse(TestCase):
    database_file = Path('resources/bivas_LSM_2018_NWMinput_lsm2bivas_v2018_02.db')

    def setUp(self):
        # Test if database exists
        if not self.database_file.exists():
            self.skipTest('Database could not be found')

        # Connect to database
        self.BIVAS = IVS90_analyse(self.database_file)
        self.BIVAS.set_scenario(47)

        self.BIVAS.outputdir = Path('export_pyBIVAS_IVS90')

    def test_plot_CountingPointsForYear(self):
        self.BIVAS.plot_CountingPointsForYear()
    def test_plot_CEMTclassesForYear(self):
        self.BIVAS.plot_CEMTclassesForYear()
    def test_plot_YearlyChanges_Timeseries(self):
        self.BIVAS.plot_YearlyChanges_Timeseries()
    def test_plot_YearlyChangesCEMT(self):
        self.BIVAS.plot_YearlyChangesCEMT()
    def test_plot_YearlyChangesRWSklasse(self):
        self.BIVAS.plot_YearlyChangesRWSklasse()
