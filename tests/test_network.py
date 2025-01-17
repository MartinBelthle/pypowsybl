#
# Copyright (c) 2020-2022, RTE (http://www.rte-france.com)
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
import copy
import unittest
import datetime
import pandas as pd
from numpy import NaN
import numpy as np

import pypowsybl as pp
import pathlib
import matplotlib.pyplot as plt
import networkx as nx
import util
import tempfile


TEST_DIR = pathlib.Path(__file__).parent
DATA_DIR = TEST_DIR.parent.joinpath('data')


class NetworkTestCase(unittest.TestCase):

    @staticmethod
    def test_print_version():
        pp.print_version()

    def test_create_empty_network(self):
        n = pp.network.create_empty("test")
        self.assertIsNotNone(n)

    def test_load_network_from_string(self):
        file_content = """
##C 2007.05.01
##N
##ZBE
BBE1AA1               0 2 400.00 3000.00 0.00000 -1500.0 0.00000 0.00000 -9000.0 9000.00 -9000.0                               F
        """
        n = pp.network.load_from_string('simple-eu.uct', file_content)
        self.assertEqual(1, len(n.get_substations()))

    def test_dump_to_string(self):
        bat_path = TEST_DIR.joinpath('battery.xiidm')
        xml = bat_path.read_text()
        n = pp.network.load(str(bat_path))
        self.assertEqual(xml, n.dump_to_string())

    def test_get_import_format(self):
        formats = pp.network.get_import_formats()
        self.assertEqual(['CGMES', 'MATPOWER', 'IEEE-CDF', 'PSS/E', 'UCTE', 'XIIDM', 'POWER-FACTORY'], formats)

    def test_get_import_parameters(self):
        parameters = pp.network.get_import_parameters('PSS/E')
        self.assertEqual(1, len(parameters))
        self.assertEqual(['psse.import.ignore-base-voltage'], parameters.index.tolist())
        self.assertEqual('Ignore base voltage specified in the file',
                         parameters['description']['psse.import.ignore-base-voltage'])
        self.assertEqual('BOOLEAN', parameters['type']['psse.import.ignore-base-voltage'])
        self.assertEqual('false', parameters['default']['psse.import.ignore-base-voltage'])

    def test_get_export_parameters(self):
        parameters = pp.network.get_export_parameters('CGMES')
        print(parameters.index.tolist())
        self.assertEqual(4, len(parameters))
        name = 'iidm.export.cgmes.export-boundary-power-flows'
        self.assertEqual(name, parameters.index.tolist()[1])
        self.assertEqual(
            'Export boundaries\' power flows',
            parameters['description'][name])
        self.assertEqual('BOOLEAN', parameters['type'][name])
        self.assertEqual('true', parameters['default'][name])

    def test_get_export_format(self):
        formats = pp.network.get_export_formats()
        self.assertEqual(['CGMES', 'PSS/E', 'UCTE', 'XIIDM'], formats)

    def test_load_network(self):
        n = pp.network.load(str(TEST_DIR.joinpath('empty-network.xml')))
        self.assertIsNotNone(n)

    def test_load_power_factory_network(self):
        n = pp.network.load(str(DATA_DIR.joinpath('ieee14.dgs')))
        self.assertIsNotNone(n)

    def test_connect_disconnect(self):
        n = pp.network.create_ieee14()
        self.assertTrue(n.disconnect('L1-2-1'))
        self.assertTrue(n.connect('L1-2-1'))

    def test_network_attributes(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        self.assertEqual('sim1', n.id)
        self.assertEqual(datetime.datetime(2018, 1, 1, 10, 0), n.case_date)
        self.assertEqual('sim1', n.name)
        self.assertEqual(datetime.timedelta(0), n.forecast_distance)
        self.assertEqual('test', n.source_format)

    def test_network_representation(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        expected = 'Network(id=sim1, name=sim1, case_date=2018-01-01 10:00:00, ' \
                   'forecast_distance=0:00:00, source_format=test)'
        self.assertEqual(expected, str(n))
        self.assertEqual(expected, repr(n))

    def test_get_network_element_ids(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        self.assertEqual(['NGEN_NHV1', 'NHV2_NLOAD'],
                         n.get_elements_ids(pp.network.ElementType.TWO_WINDINGS_TRANSFORMER))
        self.assertEqual(['NGEN_NHV1'], n.get_elements_ids(element_type=pp.network.ElementType.TWO_WINDINGS_TRANSFORMER,
                                                           nominal_voltages={24}))
        self.assertEqual(['NGEN_NHV1', 'NHV2_NLOAD'],
                         n.get_elements_ids(element_type=pp.network.ElementType.TWO_WINDINGS_TRANSFORMER,
                                            nominal_voltages={24, 150}))
        self.assertEqual(['LOAD'], n.get_elements_ids(element_type=pp.network.ElementType.LOAD, nominal_voltages={150}))
        self.assertEqual(['LOAD'], n.get_elements_ids(element_type=pp.network.ElementType.LOAD, nominal_voltages={150},
                                                      countries={'BE'}))
        self.assertEqual([], n.get_elements_ids(element_type=pp.network.ElementType.LOAD, nominal_voltages={150},
                                                countries={'FR'}))
        self.assertEqual(['NGEN_NHV1'], n.get_elements_ids(element_type=pp.network.ElementType.TWO_WINDINGS_TRANSFORMER,
                                                           nominal_voltages={24}, countries={'FR'}))
        self.assertEqual([], n.get_elements_ids(element_type=pp.network.ElementType.TWO_WINDINGS_TRANSFORMER,
                                                nominal_voltages={24}, countries={'BE'}))

    def test_buses(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        buses = n.get_buses()
        expected = pd.DataFrame(index=pd.Series(name='id', data=['VLGEN_0', 'VLHV1_0', 'VLHV2_0', 'VLLOAD_0']),
                                columns=['name', 'v_mag', 'v_angle', 'connected_component', 'synchronous_component',
                                         'voltage_level_id'],
                                data=[['', NaN, NaN, 0, 0, 'VLGEN'],
                                      ['', 380, NaN, 0, 0, 'VLHV1'],
                                      ['', 380, NaN, 0, 0, 'VLHV2'],
                                      ['', NaN, NaN, 0, 0, 'VLLOAD']])
        pd.testing.assert_frame_equal(expected, buses, check_dtype=False)

        n.update_buses(pd.DataFrame(index=['VLGEN_0'], columns=['v_mag', 'v_angle'], data=[[400, 0]]))
        buses = n.get_buses()
        expected = pd.DataFrame(index=pd.Series(name='id', data=['VLGEN_0', 'VLHV1_0', 'VLHV2_0', 'VLLOAD_0']),
                                columns=['name', 'v_mag', 'v_angle', 'connected_component', 'synchronous_component',
                                         'voltage_level_id'],
                                data=[['', 400, 0, 0, 0, 'VLGEN'],
                                      ['', 380, NaN, 0, 0, 'VLHV1'],
                                      ['', 380, NaN, 0, 0, 'VLHV2'],
                                      ['', NaN, NaN, 0, 0, 'VLLOAD']])
        pd.testing.assert_frame_equal(expected, buses, check_dtype=False)

    def test_loads_data_frame(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        loads = n.get_loads()
        self.assertEqual(600, loads['p0']['LOAD'])
        self.assertEqual(200, loads['q0']['LOAD'])
        self.assertEqual('UNDEFINED', loads['type']['LOAD'])
        df2 = pd.DataFrame(data=[[500, 300]], columns=['p0', 'q0'], index=['LOAD'])
        n.update_loads(df2)
        df3 = n.get_loads()
        self.assertEqual(300, df3['q0']['LOAD'])
        self.assertEqual(500, df3['p0']['LOAD'])

    def test_batteries_data_frame(self):
        n = pp.network.load(str(TEST_DIR.joinpath('battery.xiidm')))
        batteries = n.get_batteries()
        self.assertEqual(200.0, batteries['max_p']['BAT2'])
        df2 = pd.DataFrame(data=[[101, 201]], columns=['p0', 'q0'], index=['BAT2'])
        n.update_batteries(df2)
        df3 = n.get_batteries()
        self.assertEqual(101, df3['p0']['BAT2'])
        self.assertEqual(201, df3['q0']['BAT2'])

    def test_vsc_data_frame(self):
        n = pp.network.create_four_substations_node_breaker_network()
        stations = n.get_vsc_converter_stations()
        self.assertEqual(400.0, stations['target_v']['VSC1'])
        self.assertEqual(500.0, stations['target_q']['VSC1'])
        stations2 = pd.DataFrame(data=[[300.0, 400.0], [1.0, 2.0]],
                                 columns=['target_v', 'target_q'], index=['VSC1', 'VSC2'])
        n.update_vsc_converter_stations(stations2)
        stations = n.get_vsc_converter_stations()
        self.assertEqual(300.0, stations['target_v']['VSC1'])
        self.assertEqual(400.0, stations['target_q']['VSC1'])
        self.assertEqual(1.0, stations['target_v']['VSC2'])
        self.assertEqual(2.0, stations['target_q']['VSC2'])
        self.assertAlmostEqual(1.1, stations['loss_factor']['VSC1'], delta=0.001)
        self.assertAlmostEqual(1.1, stations['loss_factor']['VSC2'], delta=0.001)

    def test_lcc_data_frame(self):
        n = pp.network.create_four_substations_node_breaker_network()
        stations = n.get_lcc_converter_stations()

        expected = pd.DataFrame(index=pd.Series(name='id', data=['LCC1', 'LCC2']),
                                columns=['name', 'power_factor', 'loss_factor', 'p', 'q', 'i', 'voltage_level_id',
                                         'bus_id', 'connected'],
                                data=[['LCC1', 0.6, 1.1, 80.88, NaN, NaN, 'S1VL2', 'S1VL2_0', True],
                                      ['LCC2', 0.6, 1.1, - 79.12, NaN, NaN, 'S3VL1', 'S3VL1_0', True]])
        pd.testing.assert_frame_equal(expected, stations, check_dtype=False)
        n.update_lcc_converter_stations(
            pd.DataFrame(index=['LCC1'],
                         columns=['power_factor', 'loss_factor', 'p', 'q'],
                         data=[[0.7, 1.2, 82, 69]]))
        expected = pd.DataFrame(index=pd.Series(name='id',
                                                data=['LCC1', 'LCC2']),
                                columns=['name', 'power_factor', 'loss_factor', 'p', 'q', 'i', 'voltage_level_id',
                                         'bus_id', 'connected'],
                                data=[['LCC1', 0.7, 1.2, 82, 69, 154.68, 'S1VL2', 'S1VL2_0', True],
                                      ['LCC2', 0.6, 1.1, - 79.12, NaN, NaN, 'S3VL1', 'S3VL1_0', True]])
        pd.testing.assert_frame_equal(expected, n.get_lcc_converter_stations(), check_dtype=False, atol=10 ** -2)

    def test_hvdc_data_frame(self):
        n = pp.network.create_four_substations_node_breaker_network()
        lines = n.get_hvdc_lines()
        self.assertEqual(10, lines['target_p']['HVDC1'])
        lines2 = pd.DataFrame(data=[11], columns=['target_p'], index=['HVDC1'])
        n.update_hvdc_lines(lines2)
        lines = n.get_hvdc_lines()
        self.assertEqual(11, lines['target_p']['HVDC1'])

    def test_svc_data_frame(self):
        n = pp.network.create_four_substations_node_breaker_network()
        svcs = n.get_static_var_compensators()
        expected = pd.DataFrame(
            index=pd.Series(name='id', data=['SVC']),
            columns=['name', 'b_min', 'b_max', 'target_v', 'target_q',
                     'regulation_mode', 'p', 'q', 'i', 'voltage_level_id', 'bus_id',
                     'connected'],
            data=[['', -0.05, 0.05, 400, NaN, 'VOLTAGE', NaN, -12.54, NaN, 'S4VL1', 'S4VL1_0', True]])
        pd.testing.assert_frame_equal(expected, svcs, check_dtype=False, atol=10 ** -2)
        n.update_static_var_compensators(pd.DataFrame(
            index=pd.Series(name='id', data=['SVC']),
            columns=['b_min', 'b_max', 'target_v', 'target_q', 'regulation_mode', 'p', 'q'],
            data=[[-0.06, 0.06, 398, 100, 'REACTIVE_POWER', -12, -13]]))

        svcs = n.get_static_var_compensators()
        expected = pd.DataFrame(
            index=pd.Series(name='id', data=['SVC']),
            columns=['name', 'b_min', 'b_max', 'target_v', 'target_q', 'regulation_mode', 'p', 'q', 'i',
                     'voltage_level_id', 'bus_id', 'connected'],
            data=[['', -0.06, 0.06, 398, 100, 'REACTIVE_POWER', -12, -13, 25.54, 'S4VL1', 'S4VL1_0', True]])
        pd.testing.assert_frame_equal(expected, svcs, check_dtype=False, atol=10 ** -2)

    def test_create_generators_data_frame(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        generators = n.get_generators()
        self.assertEqual('OTHER', generators['energy_source']['GEN'])
        self.assertEqual(607, generators['target_p']['GEN'])

    def test_ratio_tap_changer_steps_data_frame(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        steps = n.get_ratio_tap_changer_steps()
        self.assertEqual(0.8505666905244191, steps.loc['NHV2_NLOAD']['rho'][0])
        self.assertEqual(0.8505666905244191, steps.loc[('NHV2_NLOAD', 0), 'rho'])
        expected = pd.DataFrame(
            index=pd.MultiIndex.from_tuples([('NHV2_NLOAD', 0), ('NHV2_NLOAD', 1), ('NHV2_NLOAD', 2)],
                                            names=['id', 'position']),
            columns=['rho', 'r', 'x', 'g', 'b'],
            data=[[0.850567, 0, 0, 0, 0],
                  [1.00067, 0, 0, 0, 0],
                  [1.15077, 0, 0, 0, 0]])
        pd.testing.assert_frame_equal(expected, steps, check_dtype=False)
        n.update_ratio_tap_changer_steps(pd.DataFrame(
            index=pd.MultiIndex.from_tuples([('NHV2_NLOAD', 0), ('NHV2_NLOAD', 1)],
                                            names=['id', 'position']), columns=['rho', 'r', 'x', 'g', 'b'],
            data=[[1, 1, 1, 1, 1],
                  [1, 1, 1, 1, 1]]))
        expected = pd.DataFrame(
            index=pd.MultiIndex.from_tuples([('NHV2_NLOAD', 0), ('NHV2_NLOAD', 1), ('NHV2_NLOAD', 2)],
                                            names=['id', 'position']),
            columns=['rho', 'r', 'x', 'g', 'b'],
            data=[[1, 1, 1, 1, 1],
                  [1, 1, 1, 1, 1],
                  [1.15077, 0, 0, 0, 0]])
        pd.testing.assert_frame_equal(expected, n.get_ratio_tap_changer_steps(), check_dtype=False)
        n.update_ratio_tap_changer_steps(id='NHV2_NLOAD', position=0, rho=2, r=3, x=4, g=5, b=6)

        expected = pd.DataFrame.from_records(
            index=['id', 'position'],
            columns=['id', 'position', 'rho', 'r', 'x', 'g', 'b'],
            data=[('NHV2_NLOAD', 0, 2, 3, 4, 5, 6),
                  ('NHV2_NLOAD', 1, 1, 1, 1, 1, 1),
                  ('NHV2_NLOAD', 2, 1.15077, 0, 0, 0, 0)])

        pd.testing.assert_frame_equal(expected, n.get_ratio_tap_changer_steps(), check_dtype=False)

    def test_phase_tap_changer_steps_data_frame(self):
        n = pp.network.create_ieee300()
        steps = n.get_phase_tap_changer_steps()
        self.assertEqual(11.4, steps.loc[('T196-2040-1', 0), 'alpha'])
        expected = pd.DataFrame(
            index=pd.MultiIndex.from_tuples([('T196-2040-1', 0)],
                                            names=['id', 'position']),
            columns=['rho', 'alpha', 'r', 'x', 'g', 'b'],
            data=[[1, 11.4, 0, 0, 0, 0]])
        pd.testing.assert_frame_equal(expected, n.get_phase_tap_changer_steps(), check_dtype=False)
        n.update_phase_tap_changer_steps(pd.DataFrame(
            index=pd.MultiIndex.from_tuples([('T196-2040-1', 0)],
                                            names=['id', 'position']), columns=['alpha', 'rho', 'r', 'x', 'g', 'b'],
            data=[[1, 1, 1, 1, 1, 1]]))
        expected = pd.DataFrame(
            index=pd.MultiIndex.from_tuples([('T196-2040-1', 0)],
                                            names=['id', 'position']),
            columns=['rho', 'alpha', 'r', 'x', 'g', 'b'],
            data=[[1, 1, 1, 1, 1, 1]])
        pd.testing.assert_frame_equal(expected, n.get_phase_tap_changer_steps(), check_dtype=False)
        n.update_phase_tap_changer_steps(id=['T196-2040-1'], position=[0], rho=[2], alpha=[7], r=[3], x=[4], g=[5],
                                         b=[6])
        expected = pd.DataFrame(
            index=pd.MultiIndex.from_tuples([('T196-2040-1', 0)],
                                            names=['id', 'position']),
            columns=['rho', 'alpha', 'r', 'x', 'g', 'b'],
            data=[[2, 7, 3, 4, 5, 6]])
        pd.testing.assert_frame_equal(expected, n.get_phase_tap_changer_steps(), check_dtype=False)

    def test_update_generators_data_frame(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        generators = n.get_generators()
        self.assertEqual(607, generators['target_p']['GEN'])
        self.assertTrue(generators['voltage_regulator_on']['GEN'])
        self.assertEqual('', generators['regulated_element_id']['GEN'])
        generators2 = pd.DataFrame(data=[[608.0, 302.0, 25.0, False]],
                                   columns=['target_p', 'target_q', 'target_v', 'voltage_regulator_on'], index=['GEN'])
        n.update_generators(generators2)
        generators = n.get_generators()
        self.assertEqual(608, generators['target_p']['GEN'])
        self.assertEqual(302.0, generators['target_q']['GEN'])
        self.assertEqual(25.0, generators['target_v']['GEN'])
        self.assertFalse(generators['voltage_regulator_on']['GEN'])

    def test_regulated_terminal_node_breaker(self):
        n = pp.network.create_four_substations_node_breaker_network()
        gens = n.get_generators()
        print(n.get_lines())
        self.assertEqual('GH1', gens['regulated_element_id']['GH1'])

        n.update_generators(id='GH1', regulated_element_id='S1VL1_BBS')
        updated_gens = n.get_generators()
        self.assertEqual('S1VL1_BBS', updated_gens['regulated_element_id']['GH1'])

        with self.assertRaises(pp.PyPowsyblError):
            n.update_generators(id='GH1', regulated_element_id='LINE_S2S3')

    def test_regulated_terminal_bus_breaker(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        generators = n.get_generators()
        self.assertEqual('', generators['regulated_element_id']['GEN'])

        with self.assertRaises(pp.PyPowsyblError):
            n.update_generators(id='GEN', regulated_element_id='NHV1')
        with self.assertRaises(pp.PyPowsyblError):
            n.update_generators(id='GEN', regulated_element_id='LOAD')

    def test_update_unknown_data(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        update = pd.DataFrame(data=[['blob']], columns=['unknown'], index=['GEN'])
        with self.assertRaises(ValueError) as context:
            n.update_generators(update)
        self.assertIn('No column named unknown', str(context.exception.args))

    def test_update_non_modifiable_data(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        update = pd.DataFrame(data=[['blob']], columns=['voltage_level_id'], index=['GEN'])
        with self.assertRaises(pp.PyPowsyblError) as context:
            n.update_generators(update)
        self.assertIn('Series \'voltage_level_id\' is not modifiable.', str(context.exception.args))

    def test_update_switches_data_frame(self):
        n = pp.network.load(str(TEST_DIR.joinpath('node-breaker.xiidm')))
        switches = n.get_switches()
        # no open switch
        open_switches = switches[switches['open']].index.tolist()
        self.assertEqual(0, len(open_switches))
        # open 1 breaker
        n.update_switches(pd.DataFrame(index=['BREAKER-BB2-VL1_VL2_1'], data={'open': [True]}))
        switches = n.get_switches()
        open_switches = switches[switches['open']].index.tolist()
        self.assertEqual(['BREAKER-BB2-VL1_VL2_1'], open_switches)

    def test_update_2_windings_transformers_data_frame(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        df = n.get_2_windings_transformers()
        self.assertEqual(
            ['name', 'r', 'x', 'g', 'b', 'rated_u1', 'rated_u2', 'rated_s', 'p1', 'q1', 'i1', 'p2', 'q2', 'i2',
             'voltage_level1_id', 'voltage_level2_id', 'bus1_id', 'bus2_id', 'connected1', 'connected2'],
            df.columns.tolist())
        expected = pd.DataFrame(index=pd.Series(name='id', data=['NGEN_NHV1', 'NHV2_NLOAD']),
                                columns=['name', 'r', 'x', 'g', 'b', 'rated_u1', 'rated_u2', 'rated_s', 'p1', 'q1',
                                         'i1', 'p2',
                                         'q2', 'i2', 'voltage_level1_id', 'voltage_level2_id', 'bus1_id', 'bus2_id',
                                         'connected1', 'connected2'],
                                data=[['', 0.27, 11.10, 0, 0, 24, 400, NaN, NaN, NaN, NaN, NaN, NaN,
                                       NaN, 'VLGEN', 'VLHV1', 'VLGEN_0', 'VLHV1_0', True, True],
                                      ['', 0.05, 4.05, 0, 0, 400, 158, NaN, NaN, NaN, NaN, NaN, NaN, NaN,
                                       'VLHV2', 'VLLOAD', 'VLHV2_0', 'VLLOAD_0', True, True]])
        pd.testing.assert_frame_equal(expected, n.get_2_windings_transformers(), check_dtype=False, atol=10 ** -2)
        n.update_2_windings_transformers(
            pd.DataFrame(index=['NGEN_NHV1'],
                         columns=['r', 'x', 'g', 'b', 'rated_u1', 'rated_u2', 'connected1', 'connected2'],
                         data=[[0.3, 11.2, 1, 1, 90, 225, False, False]]))
        expected = pd.DataFrame(index=pd.Series(name='id', data=['NGEN_NHV1', 'NHV2_NLOAD']),
                                columns=['name', 'r', 'x', 'g', 'b', 'rated_u1', 'rated_u2', 'rated_s', 'p1', 'q1',
                                         'i1', 'p2',
                                         'q2', 'i2', 'voltage_level1_id', 'voltage_level2_id', 'bus1_id', 'bus2_id',
                                         'connected1', 'connected2'],
                                data=[['', 0.3, 11.2, 1, 1, 90, 225, NaN, NaN, NaN, NaN, NaN, NaN, NaN,
                                       'VLGEN', 'VLHV1', '', '', False, False],
                                      ['', 0.047, 4.05, 0, 0, 400, 158, NaN, NaN, NaN, NaN, NaN, NaN, NaN,
                                       'VLHV2', 'VLLOAD', 'VLHV2_0', 'VLLOAD_0', True, True]])
        pd.testing.assert_frame_equal(expected, n.get_2_windings_transformers(), check_dtype=False, atol=10 ** -2)

    def test_voltage_levels_data_frame(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        voltage_levels = n.get_voltage_levels()
        self.assertEqual(24.0, voltage_levels['nominal_v']['VLGEN'])

    def test_substations_data_frame(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        expected = pd.DataFrame(index=pd.Series(name='id', data=['P1', 'P2']),
                                columns=['name', 'TSO', 'geo_tags', 'country'],
                                data=[['', 'RTE', 'A', 'FR'],
                                      ['', 'RTE', 'B', 'BE']])
        pd.testing.assert_frame_equal(expected, n.get_substations(), check_dtype=False, atol=10 ** -2)
        n.update_substations(id='P2', TSO='REE', country='ES')
        expected = pd.DataFrame(index=pd.Series(name='id', data=['P1', 'P2']),
                                columns=['name', 'TSO', 'geo_tags', 'country'],
                                data=[['', 'RTE', 'A', 'FR'],
                                      ['', 'REE', 'B', 'ES']])
        pd.testing.assert_frame_equal(expected, n.get_substations(), check_dtype=False, atol=10 ** -2)

    def test_reactive_capability_curve_points_data_frame(self):
        n = pp.network.create_four_substations_node_breaker_network()
        points = n.get_reactive_capability_curve_points()
        self.assertAlmostEqual(0, points.loc['GH1']['p'][0])
        self.assertAlmostEqual(100, points.loc['GH1']['p'][1])
        self.assertAlmostEqual(-769.3, points.loc['GH1']['min_q'][0])
        self.assertAlmostEqual(-864.55, points.loc['GH1']['min_q'][1])
        self.assertAlmostEqual(860, points.loc['GH1']['max_q'][0])
        self.assertAlmostEqual(946.25, points.loc['GH1']['max_q'][1])

    def test_exception(self):
        n = pp.network.create_ieee14()
        try:
            n.open_switch("aa")
            self.fail()
        except pp.PyPowsyblError as e:
            self.assertEqual("Switch 'aa' not found", str(e))

    def test_ratio_tap_changers(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        expected = pd.DataFrame(index=pd.Series(name='id', data=['NHV2_NLOAD']),
                                columns=['tap', 'low_tap', 'high_tap', 'step_count', 'on_load', 'regulating',
                                         'target_v', 'target_deadband', 'regulating_bus_id', 'rho',
                                         'alpha'],
                                data=[[1, 0, 2, 3, True, True, 158.0, 0.0, 'VLLOAD_0', 0.4, NaN]])
        pd.testing.assert_frame_equal(expected, n.get_ratio_tap_changers(), check_dtype=False, atol=10 ** -2)
        update = pd.DataFrame(index=['NHV2_NLOAD'],
                              columns=['tap', 'regulating', 'target_v'],
                              data=[[0, False, 180]])
        n.update_ratio_tap_changers(update)
        expected = pd.DataFrame(index=pd.Series(name='id', data=['NHV2_NLOAD']),
                                columns=['tap', 'low_tap', 'high_tap', 'step_count', 'on_load', 'regulating',
                                         'target_v', 'target_deadband', 'regulating_bus_id', 'rho',
                                         'alpha'],
                                data=[[0, 0, 2, 3, True, False, 180.0, 0.0, 'VLLOAD_0', 0.34, NaN]])
        pd.testing.assert_frame_equal(expected, n.get_ratio_tap_changers(), check_dtype=False, atol=10 ** -2)

    def test_phase_tap_changers(self):
        n = pp.network.create_four_substations_node_breaker_network()
        tap_changers = n.get_phase_tap_changers()
        self.assertEqual(['tap', 'low_tap', 'high_tap', 'step_count', 'regulating', 'regulation_mode',
                          'regulation_value', 'target_deadband', 'regulating_bus_id'], tap_changers.columns.tolist())
        twt_values = tap_changers.loc['TWT']
        self.assertEqual(15, twt_values.tap)
        self.assertEqual(0, twt_values.low_tap)
        self.assertEqual(32, twt_values.high_tap)
        self.assertEqual(33, twt_values.step_count)
        self.assertEqual(False, twt_values.regulating)
        self.assertEqual('FIXED_TAP', twt_values.regulation_mode)
        self.assertTrue(pd.isna(twt_values.regulation_value))
        self.assertTrue(pd.isna(twt_values.target_deadband))
        update = pd.DataFrame(index=['TWT'],
                              columns=['tap', 'target_deadband', 'regulation_value', 'regulation_mode', 'regulating'],
                              data=[[10, 100, 1000, 'CURRENT_LIMITER', True]])
        n.update_phase_tap_changers(update)
        tap_changers = n.get_phase_tap_changers()
        self.assertEqual(['tap', 'low_tap', 'high_tap', 'step_count', 'regulating', 'regulation_mode',
                          'regulation_value', 'target_deadband', 'regulating_bus_id'], tap_changers.columns.tolist())
        twt_values = tap_changers.loc['TWT']
        self.assertEqual(10, twt_values.tap)
        self.assertEqual(True, twt_values.regulating)
        self.assertEqual('CURRENT_LIMITER', twt_values.regulation_mode)
        self.assertAlmostEqual(1000, twt_values.regulation_value, 1)
        self.assertAlmostEqual(100, twt_values.target_deadband, 1)

    def test_variant(self):
        n = pp.network.load(str(TEST_DIR.joinpath('node-breaker.xiidm')))
        self.assertEqual('InitialState', n.get_working_variant_id())
        n.clone_variant('InitialState', 'WorkingState')
        n.update_switches(pd.DataFrame(index=['BREAKER-BB2-VL1_VL2_1'], data={'open': [True]}))
        n.set_working_variant('WorkingState')
        self.assertEqual('WorkingState', n.get_working_variant_id())
        self.assertEqual(['InitialState', 'WorkingState'], n.get_variant_ids())
        self.assertEqual(0, len(n.get_switches()[n.get_switches()['open']].index.tolist()))
        n.set_working_variant('InitialState')
        n.remove_variant('WorkingState')
        self.assertEqual(['BREAKER-BB2-VL1_VL2_1'], n.get_switches()[n.get_switches()['open']].index.tolist())
        self.assertEqual('InitialState', n.get_working_variant_id())
        self.assertEqual(1, len(n.get_variant_ids()))

    def test_sld_svg(self):
        n = pp.network.create_four_substations_node_breaker_network()
        sld = n.get_single_line_diagram('S1VL1')
        self.assertRegex(sld.svg, '.*<svg.*')

    def test_sld_nad(self):
        n = pp.network.create_ieee14()
        sld = n.get_network_area_diagram()
        self.assertRegex(sld.svg, '.*<svg.*')
        sld = n.get_network_area_diagram(voltage_level_ids=None)
        self.assertRegex(sld.svg, '.*<svg.*')
        sld = n.get_network_area_diagram('VL1')
        self.assertRegex(sld.svg, '.*<svg.*')
        sld = n.get_network_area_diagram(['VL1', 'VL2'])
        self.assertRegex(sld.svg, '.*<svg.*')
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            test_svg = tmp_dir_name + "test.svg"
            n.write_network_area_diagram_svg(test_svg, None)
            n.write_network_area_diagram_svg(test_svg, ['VL1'])
            n.write_network_area_diagram_svg(test_svg, ['VL1', 'VL2'])

    def test_current_limits(self):
        network = pp.network.create_eurostag_tutorial_example1_network()
        self.assertEqual(9, len(network.get_current_limits()))
        self.assertEqual(5, len(network.get_current_limits().loc['NHV1_NHV2_1']))
        current_limit = network.get_current_limits().loc['NHV1_NHV2_1', '10\'']
        expected = pd.DataFrame(index=pd.MultiIndex.from_tuples(names=['branch_id', 'name'],
                                                                tuples=[('NHV1_NHV2_1', '10\'')]),
                                columns=['side', 'value', 'acceptable_duration', 'is_fictitious'],
                                data=[['TWO', 1200.0, 600, False]])
        pd.testing.assert_frame_equal(expected, current_limit, check_dtype=False)

    def test_deep_copy(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        copy_n = copy.deepcopy(n)
        self.assertEqual(['NGEN_NHV1', 'NHV2_NLOAD'],
                         copy_n.get_elements_ids(pp.network.ElementType.TWO_WINDINGS_TRANSFORMER))

    def test_lines(self):
        n = pp.network.create_four_substations_node_breaker_network()
        expected = pd.DataFrame(index=pd.Series(name='id', data=['LINE_S2S3', 'LINE_S3S4']),
                                columns=['name', 'r', 'x', 'g1', 'b1', 'g2', 'b2', 'p1', 'q1', 'i1', 'p2', 'q2', 'i2',
                                         'voltage_level1_id',
                                         'voltage_level2_id', 'bus1_id', 'bus2_id', 'connected1', 'connected2'],
                                data=[
                                    ['', 0.01, 19.1, 0, 0, 0, 0, 109.889, 190.023, 309.979, -109.886, -184.517, 309.978,
                                     'S2VL1',
                                     'S3VL1',
                                     'S2VL1_0', 'S3VL1_0', True, True],
                                    ['', 0.01, 13.1, 0, 0, 0, 0, 240.004, 2.1751, 346.43, -240, 2.5415, 346.43, 'S3VL1',
                                     'S4VL1',
                                     'S3VL1_0', 'S4VL1_0', True, True]])
        pd.testing.assert_frame_equal(expected, n.get_lines(), check_dtype=False)
        lines_update = pd.DataFrame(index=['LINE_S2S3'],
                                    columns=['r', 'x', 'g1', 'b1', 'g2', 'b2', 'p1', 'q1', 'p2', 'q2'],
                                    data=[[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]])
        n.update_lines(lines_update)
        expected = pd.DataFrame(index=pd.Series(name='id', data=['LINE_S2S3', 'LINE_S3S4']),
                                columns=['name', 'r', 'x', 'g1', 'b1', 'g2', 'b2', 'p1', 'q1', 'i1', 'p2', 'q2', 'i2',
                                         'voltage_level1_id', 'voltage_level2_id', 'bus1_id', 'bus2_id', 'connected1',
                                         'connected2'],
                                data=[['', 1, 2, 3, 4, 5, 6, 7, 8, 15.011282, 9, 10, 19.418634,
                                       'S2VL1', 'S3VL1', 'S2VL1_0', 'S3VL1_0', True, True],
                                      ['', 0.01, 13.1, 0, 0, 0, 0, 240.004, 2.1751, 346.429584, -240, 2.5415,
                                       346.429584, 'S3VL1', 'S4VL1', 'S3VL1_0', 'S4VL1_0', True, True]])
        pd.testing.assert_frame_equal(expected, n.get_lines(), check_dtype=False)

    def test_dangling_lines(self):
        n = util.create_dangling_lines_network()
        expected = pd.DataFrame(index=pd.Series(name='id', data=['DL']),
                                columns=['name', 'r', 'x', 'g', 'b', 'p0', 'q0', 'p', 'q', 'i', 'voltage_level_id',
                                         'bus_id',
                                         'connected', 'ucte-x-node-code'],
                                data=[['', 10.0, 1.0, 0.0001, 0.00001, 50.0, 30.0, NaN, NaN, NaN, 'VL', 'VL_0', True,
                                       '']])

        pd.testing.assert_frame_equal(expected, n.get_dangling_lines(), check_dtype=False)
        n.update_dangling_lines(
            pd.DataFrame(index=['DL'], columns=['r', 'x', 'g', 'b', 'p0', 'q0', 'connected'],
                         data=[[11.0, 1.1, 0.0002, 0.00002, 40.0, 40.0, False]]))
        updated = pd.DataFrame(index=pd.Series(name='id', data=['DL']),
                               columns=['name', 'r', 'x', 'g', 'b', 'p0', 'q0', 'p', 'q', 'i', 'voltage_level_id',
                                        'bus_id',
                                        'connected', 'ucte-x-node-code'],
                               data=[['', 11.0, 1.1, 0.0002, 0.00002, 40.0, 40.0, NaN, NaN, NaN, 'VL', '', False, '']])
        pd.testing.assert_frame_equal(updated, n.get_dangling_lines(), check_dtype=False)

    def test_batteries(self):
        n = util.create_battery_network()
        expected = pd.DataFrame(index=pd.Series(name='id', data=['BAT', 'BAT2']),
                                columns=['name', 'max_p', 'min_p', 'p0', 'q0', 'p', 'q', 'i', 'voltage_level_id',
                                         'bus_id',
                                         'connected'],
                                data=[['', 9999.99, -9999.99, 9999.99, 9999.99, -605, -225, NaN, 'VLBAT', 'VLBAT_0',
                                       True],
                                      ['', 200, -200, 100, 200, -605, -225, NaN, 'VLBAT', 'VLBAT_0', True]])
        pd.testing.assert_frame_equal(expected, n.get_batteries(), check_dtype=False)
        n.update_batteries(pd.DataFrame(index=['BAT2'], columns=['p0', 'q0'], data=[[50, 100]]))
        expected = pd.DataFrame(index=pd.Series(name='id', data=['BAT', 'BAT2']),
                                columns=['name', 'max_p', 'min_p', 'p0', 'q0', 'p', 'q', 'i', 'voltage_level_id',
                                         'bus_id',
                                         'connected'],
                                data=[['', 9999.99, -9999.99, 9999.99, 9999.99, -605, -225, NaN, 'VLBAT', 'VLBAT_0',
                                       True],
                                      ['', 200, -200, 50, 100, -605, -225, NaN, 'VLBAT', 'VLBAT_0', True]])
        pd.testing.assert_frame_equal(expected, n.get_batteries(), check_dtype=False)

    def test_shunt(self):
        n = pp.network.create_four_substations_node_breaker_network()
        expected = pd.DataFrame(index=pd.Series(name='id', data=['SHUNT']),
                                columns=['name', 'g', 'b', 'model_type', 'max_section_count', 'section_count',
                                         'voltage_regulation_on', 'target_v',
                                         'target_deadband', 'regulating_bus_id', 'p', 'q', 'i',
                                         'voltage_level_id', 'bus_id', 'connected'],
                                data=[['', 0.0, -0.012, 'LINEAR', 1, 1, False, NaN, NaN,
                                       'S1VL2_0', NaN, 1920, NaN, 'S1VL2', 'S1VL2_0', True]])
        pd.testing.assert_frame_equal(expected, n.get_shunt_compensators(), check_dtype=False)
        n.update_shunt_compensators(
            pd.DataFrame(index=['SHUNT'],
                         columns=['q', 'section_count', 'target_v', 'target_deadband',
                                  'connected'],
                         data=[[1900, 0, 50, 3, False]]))
        n.update_shunt_compensators(
            pd.DataFrame(index=['SHUNT'],
                         columns=['voltage_regulation_on'],
                         data=[[True]]))
        expected = pd.DataFrame(index=pd.Series(name='id', data=['SHUNT']),
                                columns=['name', 'g', 'b', 'model_type', 'max_section_count', 'section_count',
                                         'voltage_regulation_on', 'target_v',
                                         'target_deadband', 'regulating_bus_id', 'p', 'q', 'i',
                                         'voltage_level_id', 'bus_id', 'connected'],
                                data=[['', 0.0, -0.0, 'LINEAR', 1, 0, True, 50, 3,
                                       '', NaN, 1900, NaN, 'S1VL2', '', False]])
        pd.testing.assert_frame_equal(expected, n.get_shunt_compensators(), check_dtype=False)

    def test_3_windings_transformers(self):
        n = util.create_three_windings_transformer_network()
        expected = pd.DataFrame(index=pd.Series(name='id', data=['3WT']),
                                columns=['name', 'rated_u0', 'r1', 'x1', 'g1', 'b1', 'rated_u1', 'rated_s1',
                                         'ratio_tap_position1', 'phase_tap_position1', 'p1', 'q1', 'i1',
                                         'voltage_level1_id', 'bus1_id', 'connected1', 'r2', 'x2', 'g2', 'b2',
                                         'rated_u2', 'rated_s2', 'ratio_tap_position2', 'phase_tap_position2', 'p2',
                                         'q2', 'i2', 'voltage_level2_id', 'bus2_id', 'connected2', 'r3', 'x3', 'g3',
                                         'b3', 'rated_u3', 'rated_s3', 'ratio_tap_position3', 'phase_tap_position3',
                                         'p3', 'q3', 'i3', 'voltage_level3_id', 'bus3_id', 'connected3'],
                                data=[['', 132, 17.424, 1.7424, 0.00573921, 0.000573921, 132, NaN, -99999, -99999, NaN,
                                       NaN,
                                       NaN, 'VL_132', 'VL_132_0', True, 1.089, 0.1089, 0, 0, 33, NaN, 2, -99999, NaN,
                                       NaN, NaN, 'VL_33', 'VL_33_0', True, 0.121, 0.0121, 0, 0, 11, NaN, 0, -99999, NaN,
                                       NaN, NaN, 'VL_11', 'VL_11_0', True]])
        pd.testing.assert_frame_equal(expected, n.get_3_windings_transformers(), check_dtype=False)
        # test update

    def test_busbar_sections(self):
        n = pp.network.create_four_substations_node_breaker_network()
        expected = pd.DataFrame(index=pd.Series(name='id',
                                                data=['S1VL1_BBS', 'S1VL2_BBS1', 'S1VL2_BBS2', 'S2VL1_BBS', 'S3VL1_BBS',
                                                      'S4VL1_BBS']),
                                columns=['name', 'fictitious', 'v', 'angle', 'voltage_level_id', 'connected'],
                                data=[['S1VL1_BBS', False, 224.6139, 2.2822, 'S1VL1', True],
                                      ['S1VL2_BBS1', False, 400.0000, 0.0000, 'S1VL2', True],
                                      ['S1VL2_BBS2', False, 400.0000, 0.0000, 'S1VL2', True],
                                      ['S2VL1_BBS', False, 408.8470, 0.7347, 'S2VL1', True],
                                      ['S3VL1_BBS', False, 400.0000, 0.0000, 'S3VL1', True],
                                      ['S4VL1_BBS', False, 400.0000, -1.1259, 'S4VL1', True]])
        pd.testing.assert_frame_equal(expected, n.get_busbar_sections(), check_dtype=False)

        n.update_busbar_sections(
            pd.DataFrame(index=['S1VL1_BBS'],
                         columns=['fictitious'],
                         data=[[True]]))
        expected = pd.DataFrame(index=pd.Series(name='id',
                                                data=['S1VL1_BBS', 'S1VL2_BBS1', 'S1VL2_BBS2', 'S2VL1_BBS', 'S3VL1_BBS',
                                                      'S4VL1_BBS']),
                                columns=['name', 'fictitious', 'v', 'angle', 'voltage_level_id', 'connected'],
                                data=[['S1VL1_BBS', True, 224.6139, 2.2822, 'S1VL1', True],
                                      ['S1VL2_BBS1', False, 400.0000, 0.0000, 'S1VL2', True],
                                      ['S1VL2_BBS2', False, 400.0000, 0.0000, 'S1VL2', True],
                                      ['S2VL1_BBS', False, 408.8470, 0.7347, 'S2VL1', True],
                                      ['S3VL1_BBS', False, 400.0000, 0.0000, 'S3VL1', True],
                                      ['S4VL1_BBS', False, 400.0000, -1.1259, 'S4VL1', True]])
        pd.testing.assert_frame_equal(expected, n.get_busbar_sections(), check_dtype=False)

    def test_non_linear_shunt(self):
        n = util.create_non_linear_shunt_network()
        expected = pd.DataFrame(index=pd.MultiIndex.from_tuples([('SHUNT', 0), ('SHUNT', 1)],
                                                                names=['id', 'section']),
                                columns=['g', 'b'],
                                data=[[0.0, 0.00001],
                                      [0.3, 0.02000]])
        pd.testing.assert_frame_equal(expected, n.get_non_linear_shunt_compensator_sections(), check_dtype=False)
        update = pd.DataFrame(index=pd.MultiIndex.from_tuples([('SHUNT', 0), ('SHUNT', 1)], names=['id', 'section']),
                              columns=['g', 'b'],
                              data=[[0.1, 0.00002],
                                    [0.4, 0.03]])
        n.update_non_linear_shunt_compensator_sections(update)
        pd.testing.assert_frame_equal(update, n.get_non_linear_shunt_compensator_sections(), check_dtype=False)

    def test_voltage_levels(self):
        net = pp.network.create_eurostag_tutorial_example1_network()
        expected = pd.DataFrame(index=pd.Series(name='id',
                                                data=['VLGEN', 'VLHV1', 'VLHV2', 'VLLOAD']),
                                columns=['name', 'substation_id', 'nominal_v', 'high_voltage_limit',
                                         'low_voltage_limit'],
                                data=[['', 'P1', 24, NaN, NaN],
                                      ['', 'P1', 380, 500, 400],
                                      ['', 'P2', 380, 500, 300],
                                      ['', 'P2', 150, NaN, NaN]])
        pd.testing.assert_frame_equal(expected, net.get_voltage_levels(), check_dtype=False)
        net.update_voltage_levels(id=['VLGEN', 'VLLOAD'], nominal_v=[25, 151], high_voltage_limit=[50, 175],
                                  low_voltage_limit=[20, 125])
        expected = pd.DataFrame(index=pd.Series(name='id',
                                                data=['VLGEN', 'VLHV1', 'VLHV2', 'VLLOAD']),
                                columns=['name', 'substation_id', 'nominal_v', 'high_voltage_limit',
                                         'low_voltage_limit'],
                                data=[['', 'P1', 25, 50, 20],
                                      ['', 'P1', 380, 500, 400],
                                      ['', 'P2', 380, 500, 300],
                                      ['', 'P2', 151, 175, 125]])
        pd.testing.assert_frame_equal(expected, net.get_voltage_levels(), check_dtype=False)

    def test_update_with_keywords(self):
        n = util.create_non_linear_shunt_network()
        n.update_non_linear_shunt_compensator_sections(id='SHUNT', section=0, g=0.2, b=0.000001)
        self.assertEqual(0.2, n.get_non_linear_shunt_compensator_sections().loc['SHUNT', 0]['g'])
        self.assertEqual(0.000001, n.get_non_linear_shunt_compensator_sections().loc['SHUNT', 0]['b'])

    def test_update_generators_with_keywords(self):
        n = pp.network.create_four_substations_node_breaker_network()
        n.update_generators(id=['GTH1', 'GTH2'], target_p=[200, 300])
        self.assertEqual([200, 300], n.get_generators().loc[['GTH1', 'GTH2'], 'target_p'].to_list())

    def test_invalid_update_kwargs(self):
        n = pp.network.create_four_substations_node_breaker_network()

        with self.assertRaises(RuntimeError) as context:
            n.update_generators(df=pd.DataFrame(index=['GTH1'], columns=['target_p'], data=[300]),
                                id='GTH1', target_p=300)
        self.assertIn('only one form', str(context.exception))

        with self.assertRaises(ValueError) as context:
            n.update_generators(id=['GTH1', 'GTH2'], target_p=100)
        self.assertIn('same size', str(context.exception))

        with self.assertRaises(ValueError) as context:
            n.update_generators(id=np.array(0, ndmin=3))
        self.assertIn('dimensions', str(context.exception))

    def test_create_network(self):
        n = pp.network.create_ieee9()
        self.assertEqual('ieee9cdf', n.id)
        n = pp.network.create_ieee30()
        self.assertEqual('ieee30cdf', n.id)
        n = pp.network.create_ieee57()
        self.assertEqual('ieee57cdf', n.id)
        n = pp.network.create_ieee118()
        self.assertEqual('ieee118cdf', n.id)

    def test_node_breaker_view(self):
        n = pp.network.create_four_substations_node_breaker_network()
        topology = n.get_node_breaker_topology('S4VL1')
        switches = topology.switches
        nodes = topology.nodes
        self.assertEqual(6, len(switches))
        self.assertEqual('S4VL1_BBS_LINES3S4_DISCONNECTOR', switches.loc['S4VL1_BBS_LINES3S4_DISCONNECTOR']['name'])
        self.assertEqual('DISCONNECTOR', switches.loc['S4VL1_BBS_LINES3S4_DISCONNECTOR']['kind'])
        self.assertEqual(False, switches.loc['S4VL1_BBS_LINES3S4_DISCONNECTOR']['open'])
        self.assertEqual(0, switches.loc['S4VL1_BBS_LINES3S4_DISCONNECTOR']['node1'])
        self.assertEqual(5, switches.loc['S4VL1_BBS_LINES3S4_DISCONNECTOR']['node2'])
        self.assertEqual(7, len(nodes))
        self.assertTrue(topology.internal_connections.empty)

    def test_graph(self):
        n = pp.network.create_four_substations_node_breaker_network()
        network_topology = n.get_node_breaker_topology('S4VL1')
        graph = network_topology.create_graph()
        self.assertEqual(7, len(graph.nodes))
        self.assertEqual([(0, 5), (0, 1), (0, 3), (1, 2), (3, 4), (5, 6)], list(graph.edges))

    @unittest.skip("plot graph skipping")
    def test_node_breaker_view_draw_graph(self):
        n = pp.network.create_four_substations_node_breaker_network()
        network_topology = n.get_node_breaker_topology('S4VL1')
        graph = network_topology.create_graph()
        nx.draw_shell(graph, with_labels=True)
        plt.show()

    def test_network_merge(self):
        be = pp.network.create_micro_grid_be_network()
        self.assertEqual(6, len(be.get_voltage_levels()))
        nl = pp.network.create_micro_grid_nl_network()
        self.assertEqual(4, len(nl.get_voltage_levels()))
        be.merge(nl)
        self.assertEqual(10, len(be.get_voltage_levels()))

    def test_linear_shunt_compensator_sections(self):
        n = pp.network.create_four_substations_node_breaker_network()
        expected = pd.DataFrame(index=pd.Series(name='id',
                                                data=['SHUNT']),
                                columns=['g_per_section', 'b_per_section', 'max_section_count'],
                                data=[[NaN, -0.012, 1]])
        pd.testing.assert_frame_equal(expected, n.get_linear_shunt_compensator_sections(), check_dtype=False)
        n.update_linear_shunt_compensator_sections(
            pd.DataFrame(index=['SHUNT'],
                         columns=['g_per_section', 'b_per_section', 'max_section_count'],
                         data=[[0.14, -0.01, 4]]))
        expected = pd.DataFrame(index=pd.Series(name='id',
                                                data=['SHUNT']),
                                columns=['g_per_section', 'b_per_section', 'max_section_count'],
                                data=[[0.14, -0.01, 4]])
        pd.testing.assert_frame_equal(expected, n.get_linear_shunt_compensator_sections(), check_dtype=False)
        n.update_linear_shunt_compensator_sections(id='SHUNT', g_per_section=0.15, b_per_section=-0.02)
        self.assertEqual(0.15, n.get_linear_shunt_compensator_sections().loc['SHUNT']['g_per_section'])
        self.assertEqual(-0.02, n.get_linear_shunt_compensator_sections().loc['SHUNT']['b_per_section'])

    def test_bus_breaker_view(self):
        n = pp.network.create_four_substations_node_breaker_network()
        n.update_switches(pd.DataFrame(index=['S1VL2_COUPLER'], data={'open': [True]}))
        topology = n.get_bus_breaker_topology('S1VL2')
        switches = topology.switches
        buses = topology.buses
        elements = topology.elements
        expected_switches = pd.DataFrame(index=pd.Series(name='id',
                                                         data=['S1VL2_TWT_BREAKER', 'S1VL2_VSC1_BREAKER',
                                                               'S1VL2_GH1_BREAKER', 'S1VL2_GH2_BREAKER',
                                                               'S1VL2_GH3_BREAKER', 'S1VL2_LD2_BREAKER',
                                                               'S1VL2_LD3_BREAKER', 'S1VL2_LD4_BREAKER',
                                                               'S1VL2_SHUNT_BREAKER', 'S1VL2_LCC1_BREAKER',
                                                               'S1VL2_COUPLER']),
                                         columns=['kind', 'open', 'bus1_id', 'bus2_id'],
                                         data=[['BREAKER', False, 'S1VL2_0', 'S1VL2_3'],
                                               ['BREAKER', False, 'S1VL2_1', 'S1VL2_5'],
                                               ['BREAKER', False, 'S1VL2_0', 'S1VL2_7'],
                                               ['BREAKER', False, 'S1VL2_0', 'S1VL2_9'],
                                               ['BREAKER', False, 'S1VL2_0', 'S1VL2_11'],
                                               ['BREAKER', False, 'S1VL2_1', 'S1VL2_13'],
                                               ['BREAKER', False, 'S1VL2_1', 'S1VL2_15'],
                                               ['BREAKER', False, 'S1VL2_1', 'S1VL2_17'],
                                               ['BREAKER', False, 'S1VL2_0', 'S1VL2_19'],
                                               ['BREAKER', False, 'S1VL2_1', 'S1VL2_21'],
                                               ['BREAKER', True, 'S1VL2_0', 'S1VL2_1']])
        expected_buses = pd.DataFrame(index=pd.Series(name='id',
                                                      data=['S1VL2_0', 'S1VL2_1', 'S1VL2_3', 'S1VL2_5', 'S1VL2_7',
                                                            'S1VL2_9', 'S1VL2_11', 'S1VL2_13', 'S1VL2_15', 'S1VL2_17',
                                                            'S1VL2_19', 'S1VL2_21']),
                                      columns=['name', 'bus_id'],
                                      data=[['', 'S1VL2_0'], ['', 'S1VL2_1'], ['', 'S1VL2_0'], ['', 'S1VL2_1'],
                                            ['', 'S1VL2_0'], ['', 'S1VL2_0'], ['', 'S1VL2_0'], ['', 'S1VL2_1'],
                                            ['', 'S1VL2_1'], ['', 'S1VL2_1'], ['', 'S1VL2_0'], ['', 'S1VL2_1']])

        expected_elements = pd.DataFrame.from_records(index='id', columns=['id', 'type', 'bus_id', 'side'],
                                                      data=[
                                                          ('S1VL2_BBS1', 'BUSBAR_SECTION', 'S1VL2_0', ''),
                                                          ('S1VL2_BBS2', 'BUSBAR_SECTION', 'S1VL2_1', ''),
                                                          ('TWT', 'TWO_WINDINGS_TRANSFORMER', 'S1VL2_3', 'TWO'),
                                                          ('VSC1', 'HVDC_CONVERTER_STATION', 'S1VL2_5', ''),
                                                          ('GH1', 'GENERATOR', 'S1VL2_7', ''),
                                                          ('GH2', 'GENERATOR', 'S1VL2_9', ''),
                                                          ('GH3', 'GENERATOR', 'S1VL2_11', ''),
                                                          ('LD2', 'LOAD', 'S1VL2_13', ''),
                                                          ('LD3', 'LOAD', 'S1VL2_15', ''),
                                                          ('LD4', 'LOAD', 'S1VL2_17', ''),
                                                          ('SHUNT', 'SHUNT_COMPENSATOR', 'S1VL2_19', ''),
                                                          ('LCC1', 'HVDC_CONVERTER_STATION', 'S1VL2_21', ''),
                                                      ])
        pd.testing.assert_frame_equal(expected_switches, switches, check_dtype=False)
        pd.testing.assert_frame_equal(expected_buses, buses, check_dtype=False)
        pd.testing.assert_frame_equal(expected_elements, elements, check_dtype=False)

    def test_not_connected_bus_breaker(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        expected = pd.DataFrame.from_records(index='id', data=[{'id': 'NHV1', 'name': '', 'bus_id': 'VLHV1_0'}])
        pd.testing.assert_frame_equal(expected, n.get_bus_breaker_topology('VLHV1').buses, check_dtype=False)
        n.update_lines(id=['NHV1_NHV2_1', 'NHV1_NHV2_2'], connected1=[False, False], connected2=[False, False])
        n.update_2_windings_transformers(id='NGEN_NHV1', connected1=False, connected2=False)

        topo = n.get_bus_breaker_topology('VLHV1')
        bb_bus = topo.buses.loc['NHV1']
        self.assertEqual('', bb_bus['name'])
        self.assertEqual('', bb_bus['bus_id'])

        line = topo.elements.loc['NHV1_NHV2_1']
        self.assertEqual('', line['bus_id'])

    def test_graph_busbreakerview(self):
        n = pp.network.create_four_substations_node_breaker_network()
        network_topology = n.get_bus_breaker_topology('S4VL1')
        graph = network_topology.create_graph()
        self.assertEqual(4, len(graph.nodes))
        self.assertEqual([('S4VL1_0', 'S4VL1_6'), ('S4VL1_0', 'S4VL1_2'), ('S4VL1_0', 'S4VL1_4')], list(graph.edges))

    @unittest.skip("plot graph skipping")
    def test_bus_breaker_view_draw_graph(self):
        n = pp.network.create_four_substations_node_breaker_network()
        network_topology = n.get_bus_breaker_topology('S1VL2')
        graph = network_topology.create_graph()
        nx.draw_shell(graph, with_labels=True)
        plt.show()

    def test_dataframe_attributes_filtering(self):
        n = pp.network.create_eurostag_tutorial_example1_network()
        buses_selected_attributes = n.get_buses(attributes=['v_mag', 'voltage_level_id'])
        expected = pd.DataFrame(index=pd.Series(name='id', data=['VLGEN_0', 'VLHV1_0', 'VLHV2_0', 'VLLOAD_0']),
                                columns=['v_mag', 'voltage_level_id'],
                                data=[[NaN, 'VLGEN'],
                                      [380, 'VLHV1'],
                                      [380, 'VLHV2'],
                                      [NaN, 'VLLOAD']])
        pd.testing.assert_frame_equal(expected, buses_selected_attributes, check_dtype=False)
        buses_default_attributes = n.get_buses(all_attributes=False)
        expected_default_attributes = pd.DataFrame(
            index=pd.Series(name='id', data=['VLGEN_0', 'VLHV1_0', 'VLHV2_0', 'VLLOAD_0']),
            columns=['name', 'v_mag', 'v_angle', 'connected_component', 'synchronous_component',
                     'voltage_level_id'],
            data=[['', NaN, NaN, 0, 0, 'VLGEN'],
                  ['', 380, NaN, 0, 0, 'VLHV1'],
                  ['', 380, NaN, 0, 0, 'VLHV2'],
                  ['', NaN, NaN, 0, 0, 'VLLOAD']])
        pd.testing.assert_frame_equal(expected_default_attributes, buses_default_attributes, check_dtype=False)
        buses_default_attributes2 = n.get_buses(attributes=[])
        pd.testing.assert_frame_equal(expected_default_attributes, buses_default_attributes2, check_dtype=False)

        buses_all_attributes = n.get_buses(all_attributes=True)
        expected_all_attributes = expected_default_attributes
        pd.testing.assert_frame_equal(expected_all_attributes, buses_all_attributes, check_dtype=False)

        try:
            buses_all_attributes_conflicting_params = n.get_buses(all_attributes=True,
                                                                  attributes=['v_mag', 'voltage_level_id'])
            self.fail()
        except RuntimeError as e:
            self.assertEqual("parameters \"all_attributes\" and \"attributes\" are mutually exclusive", str(e))

    def test_metadata(self):
        meta_gen = pp._pypowsybl.get_network_elements_dataframe_metadata(pp._pypowsybl.ElementType.GENERATOR)
        meta_gen_index_default = [x for x in meta_gen if (x.is_index == True) and (x.is_default == True)]
        print(meta_gen_index_default)
        self.assertTrue(len(meta_gen_index_default) > 0)

    def test_dataframe_elements_filtering(self):
        network_four_subs = pp.network.create_four_substations_node_breaker_network()
        network_micro_grid = pp.network.create_micro_grid_be_network()
        network_eurostag = pp.network.create_eurostag_tutorial_example1_network()
        network_non_linear_shunt = util.create_non_linear_shunt_network()
        network_with_batteries = pp.network.load(str(TEST_DIR.joinpath('battery.xiidm')))

        expected_selection = network_four_subs.get_2_windings_transformers().loc[['TWT']]
        filtered_selection = network_four_subs.get_2_windings_transformers(id='TWT')
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_micro_grid.get_3_windings_transformers().loc[
            ['_84ed55f4-61f5-4d9d-8755-bba7b877a246']]
        filtered_selection = network_micro_grid.get_3_windings_transformers(
            id=['_84ed55f4-61f5-4d9d-8755-bba7b877a246'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_micro_grid.get_shunt_compensators().loc[['_002b0a40-3957-46db-b84a-30420083558f']]
        filtered_selection = network_micro_grid.get_shunt_compensators(id=['_002b0a40-3957-46db-b84a-30420083558f'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_with_batteries.get_batteries().loc[['BAT2']]
        filtered_selection = network_with_batteries.get_batteries(id=['BAT2'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_four_subs.get_busbar_sections().loc[['S1VL2_BBS2']]
        filtered_selection = network_four_subs.get_busbar_sections(id=['S1VL2_BBS2'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_four_subs.get_buses().loc[['S3VL1_0']]
        filtered_selection = network_four_subs.get_buses(id=['S3VL1_0'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_eurostag.get_generators().loc[['GEN2', 'GEN']]
        filtered_selection = network_eurostag.get_generators(id=['GEN2', 'GEN'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_four_subs.get_hvdc_lines().loc[['HVDC2']]
        filtered_selection = network_four_subs.get_hvdc_lines(id=['HVDC2'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_four_subs.get_lcc_converter_stations().loc[['LCC2']]
        filtered_selection = network_four_subs.get_lcc_converter_stations(id=['LCC2'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_four_subs.get_linear_shunt_compensator_sections().loc[['SHUNT']]
        filtered_selection = network_four_subs.get_linear_shunt_compensator_sections(id=['SHUNT'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_four_subs.get_lines().loc[['LINE_S3S4']]
        filtered_selection = network_four_subs.get_lines(id=['LINE_S3S4'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_four_subs.get_loads().loc[['LD4']]
        filtered_selection = network_four_subs.get_loads(id=['LD4'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_non_linear_shunt.get_non_linear_shunt_compensator_sections().loc[
            pd.MultiIndex.from_tuples([('SHUNT', 1)], names=['id', 'section'])]
        filtered_selection = network_non_linear_shunt.get_non_linear_shunt_compensator_sections(id=['SHUNT'],
                                                                                                section=[1])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_four_subs.get_phase_tap_changer_steps().loc[
            pd.MultiIndex.from_tuples([('TWT', 6)], names=['id', 'position'])]
        filtered_selection = network_four_subs.get_phase_tap_changer_steps(id=['TWT'], position=[6])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_four_subs.get_phase_tap_changers().loc[['TWT']]
        filtered_selection = network_four_subs.get_phase_tap_changers(id=['TWT'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_eurostag.get_ratio_tap_changer_steps().loc[
            pd.MultiIndex.from_tuples([('NHV2_NLOAD', 0), ('NHV2_NLOAD', 2)],
                                      names=['id', 'position'])]
        filtered_selection = network_eurostag.get_ratio_tap_changer_steps(id=['NHV2_NLOAD', 'NHV2_NLOAD'],
                                                                          position=[0, 2])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_eurostag.get_ratio_tap_changers().loc[['NHV2_NLOAD']]
        filtered_selection = network_eurostag.get_ratio_tap_changers(id=['NHV2_NLOAD'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_four_subs.get_static_var_compensators().loc[['SVC']]
        filtered_selection = network_four_subs.get_static_var_compensators(id=['SVC'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_eurostag.get_substations().loc[['P2']]
        filtered_selection = network_eurostag.get_substations(id=['P2'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_four_subs.get_switches().loc[
            ['S1VL2_GH1_BREAKER', 'S4VL1_BBS_SVC_DISCONNECTOR', 'S1VL2_COUPLER']]
        filtered_selection = network_four_subs.get_switches(
            id=['S1VL2_GH1_BREAKER', 'S4VL1_BBS_SVC_DISCONNECTOR', 'S1VL2_COUPLER'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_four_subs.get_voltage_levels().loc[['S2VL1']]
        filtered_selection = network_four_subs.get_voltage_levels(id=['S2VL1'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection = network_four_subs.get_vsc_converter_stations().loc[['VSC2']]
        filtered_selection = network_four_subs.get_vsc_converter_stations(id=['VSC2'])
        pd.testing.assert_frame_equal(expected_selection, filtered_selection, check_dtype=True)

        expected_selection_empty = network_four_subs.get_generators().loc[pd.Index([], name='id')]
        self.assertTrue(expected_selection_empty.empty)
        filtered_selection_empty = network_four_subs.get_generators(id=[])
        self.assertTrue(filtered_selection_empty.empty)

    def test_limits(self):
        network = util.create_dangling_lines_network()

        expected = pd.DataFrame.from_records(
            index='element_id',
            columns=['element_id', 'element_type', 'side', 'name', 'type', 'value', 'acceptable_duration', 'is_fictitious'],
            data=[('DL', 'DANGLING_LINE', 'NONE', 'permanent_limit', 'CURRENT', 100, -1, False),
                  ('DL', 'DANGLING_LINE', 'NONE', '20\'', 'CURRENT', 120, 1200, False),
                  ('DL', 'DANGLING_LINE', 'NONE', '10\'', 'CURRENT', 140, 600, False)]
        )
        pd.testing.assert_frame_equal(expected, network.get_operational_limits(), check_dtype=False)

        network = pp.network.create_eurostag_tutorial_example1_with_power_limits_network()
        expected = pd.DataFrame.from_records(
            index='element_id',
            columns=['element_id', 'element_type', 'side', 'name', 'type', 'value', 'acceptable_duration', 'is_fictitious'],
            data=[('NHV1_NHV2_1', 'LINE', 'ONE', 'permanent_limit', 'ACTIVE_POWER', 500, -1, False),
                  ('NHV1_NHV2_1', 'LINE', 'TWO', 'permanent_limit', 'ACTIVE_POWER', 1100, -1, False),
                  ('NHV1_NHV2_1', 'LINE', 'ONE', 'permanent_limit', 'APPARENT_POWER', 500, -1, False),
                  ('NHV1_NHV2_1', 'LINE', 'TWO', 'permanent_limit', 'APPARENT_POWER', 1100, -1, False)])
        limits = network.get_operational_limits().loc['NHV1_NHV2_1']
        limits = limits[limits['name'] == 'permanent_limit']
        pd.testing.assert_frame_equal(expected, limits, check_dtype=False)
        expected = pd.DataFrame.from_records(
            index='element_id',
            columns=['element_id', 'element_type', 'side', 'name', 'type', 'value', 'acceptable_duration', 'is_fictitious'],
            data=[['NHV1_NHV2_2', 'LINE', 'ONE', "20'", 'ACTIVE_POWER', 1200, 1200, False],
                  ['NHV1_NHV2_2', 'LINE', 'ONE', "20'", 'APPARENT_POWER', 1200, 1200, False]])
        limits = network.get_operational_limits().loc['NHV1_NHV2_2']
        limits = limits[limits['name'] == '20\'']
        pd.testing.assert_frame_equal(expected, limits, check_dtype=False)
        network = util.create_three_windings_transformer_with_current_limits_network()
        expected = pd.DataFrame.from_records(
            index='element_id',
            columns=['element_id', 'element_type', 'side', 'name', 'type', 'value', 'acceptable_duration', 'is_fictitious'],
            data=[['3WT', 'THREE_WINDINGS_TRANSFORMER', 'ONE', "10'", 'CURRENT', 1400, 600, False],
                  ['3WT', 'THREE_WINDINGS_TRANSFORMER', 'TWO', "10'", 'CURRENT', 140, 600, False],
                  ['3WT', 'THREE_WINDINGS_TRANSFORMER', 'THREE', "10'", 'CURRENT', 14, 600, False]])
        limits = network.get_operational_limits().loc['3WT']
        limits = limits[limits['name'] == '10\'']
        pd.testing.assert_frame_equal(expected, limits, check_dtype=False)


if __name__ == '__main__':
    unittest.main()
