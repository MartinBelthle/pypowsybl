/**
 * Copyright (c) 2020-2022, RTE (http://www.rte-france.com)
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include "pypowsybl.h"

namespace py = pybind11;

template<typename T>
void bindArray(py::module_& m, const std::string& className) {
    py::class_<T>(m, className.c_str())
            .def("__len__", [](const T& a) {
                return a.length();
            })
            .def("__iter__", [](T& a) {
                return py::make_iterator(a.begin(), a.end());
            }, py::keep_alive<0, 1>());
}

void deleteDataframe(dataframe* df) {
    for (int indice = 0 ; indice < df->series_count; indice ++) {
        series* column = df->series + indice;
        if (column->type == 0) {
            pypowsybl::deleteCharPtrPtr((char**) column->data.ptr, column->data.length);
        } else if (column->type == 1) {
            delete[] (double*) column->data.ptr;
        } else if (column->type == 2 || column->type == 3) {
            delete[] (int*) column->data.ptr;
        }
        delete[] column->name;
    }
    delete[] df->series;
    delete df;
}

std::shared_ptr<dataframe> createDataframe(py::list columnsValues, const std::vector<std::string>& columnsNames, const std::vector<int>& columnsTypes, const std::vector<bool>& isIndex) {
    int columnsNumber = columnsNames.size();
    std::shared_ptr<dataframe> dataframe(new ::dataframe(), ::deleteDataframe);
    series* columns = new series[columnsNumber];
    for (int indice = 0 ; indice < columnsNumber ; indice ++ ) {
        series* column = columns + indice;
        py::str name = (py::str) columnsNames[indice];
        column->name = strdup(((std::string) name).c_str());
        column->index = int(isIndex[indice]);
        int type = columnsTypes[indice];
        column->type = type;
        if (type == 0) {
            std::vector<std::string> values = py::cast<std::vector<std::string>>(columnsValues[indice]);
            column->data.length = values.size();
            column->data.ptr = pypowsybl::copyVectorStringToCharPtrPtr(values);
        } else if (type == 1) {
            std::vector<double> values = py::cast<std::vector<double>>(columnsValues[indice]);
            column->data.length = values.size();
            column->data.ptr = pypowsybl::copyVectorDouble(values);
        } else if (type == 2 || type == 3) {
            std::vector<int> values = py::cast<std::vector<int>>(columnsValues[indice]);
            column->data.length = values.size();
            column->data.ptr = pypowsybl::copyVectorInt(values);
        }
    }
    dataframe->series_count = columnsNumber;
    dataframe->series = columns;
    return dataframe;
}

std::shared_ptr<dataframe_array> createDataframeArray(const std::vector<dataframe*>& dataframes) {
    std::shared_ptr<dataframe_array> dataframeArray(new dataframe_array(), [](dataframe_array* dataframeToDestroy){
        delete[] dataframeToDestroy->dataframes;
        delete dataframeToDestroy;
    });
    dataframe* dataframesFinal = new dataframe[dataframes.size()];
    for (int indice = 0 ; indice < dataframes.size() ; indice ++) {
        dataframesFinal[indice] = *dataframes[indice];
    }
    dataframeArray->dataframes = dataframesFinal;
    dataframeArray->dataframes_count = dataframes.size();
    return dataframeArray;
}

void createElement(pypowsybl::JavaHandle network, const std::vector<dataframe*>& dataframes, element_type elementType) {
    std::shared_ptr<dataframe_array> dataframeArray = ::createDataframeArray(dataframes);
    pypowsybl::createElement(network, dataframeArray.get(), elementType);
}

template<typename T>
py::array seriesAsNumpyArray(const series& series) {
	//Last argument is to bind lifetime of series to the returned array
    return py::array(py::dtype::of<T>(), series.data.length, series.data.ptr, py::cast(series));
}

// Reads parameters from config (if not disabled)
std::shared_ptr<load_flow_parameters> initLoadFlowParameters() {
        load_flow_parameters* parameters = new load_flow_parameters();
        std::shared_ptr<load_flow_parameters> config_params = pypowsybl::createLoadFlowParameters();
        parameters->voltage_init_mode = config_params->voltage_init_mode;
        parameters->transformer_voltage_control_on = config_params->transformer_voltage_control_on;
        parameters->no_generator_reactive_limits = config_params->no_generator_reactive_limits;
        parameters->phase_shifter_regulation_on = config_params->phase_shifter_regulation_on;
        parameters->twt_split_shunt_admittance = config_params->twt_split_shunt_admittance;
        parameters->simul_shunt = config_params->simul_shunt;
        parameters->read_slack_bus = config_params->read_slack_bus;
        parameters->write_slack_bus = config_params->write_slack_bus;
        parameters->distributed_slack = config_params->distributed_slack;
        parameters->balance_type = config_params->balance_type;
        parameters->dc_use_transformer_ratio = config_params->dc_use_transformer_ratio;
        //copy from config so that ownership is not transferred
        std::vector<std::string> configCountries(config_params->countries_to_balance, config_params->countries_to_balance + config_params->countries_to_balance_count);
        parameters->countries_to_balance = pypowsybl::copyVectorStringToCharPtrPtr(configCountries);
        parameters->countries_to_balance_count = configCountries.size();
        parameters->connected_component_mode = config_params->connected_component_mode;
    return std::shared_ptr<load_flow_parameters>(parameters, [](load_flow_parameters* ptr){
        pypowsybl::deleteCharPtrPtr(ptr->countries_to_balance, ptr->countries_to_balance_count);
        delete ptr;
    });
}

PYBIND11_MODULE(_pypowsybl, m) {
    pypowsybl::init();

    m.doc() = "PowSyBl Python API";

    py::register_exception<pypowsybl::PyPowsyblError>(m, "PyPowsyblError");

    py::class_<pypowsybl::JavaHandle>(m, "JavaHandle");

    m.def("set_java_library_path", &pypowsybl::setJavaLibraryPath, "Set java.library.path JVM property");

    m.def("set_debug_mode", &pypowsybl::setDebugMode, "Set debug mode");

    m.def("set_config_read", &pypowsybl::setConfigRead, "Set config read mode");

    m.def("set_default_loadflow_provider", &pypowsybl::setDefaultLoadFlowProvider, "Set default loadflow provider", py::arg("provider"));

    m.def("set_default_security_analysis_provider", &pypowsybl::setDefaultSecurityAnalysisProvider, "Set default security analysis provider", py::arg("provider"));

    m.def("set_default_sensitivity_analysis_provider", &pypowsybl::setDefaultSensitivityAnalysisProvider, "Set default sensitivity analysis provider", py::arg("provider"));

    m.def("is_config_read", &pypowsybl::isConfigRead, "Get config read mode");

    m.def("get_default_loadflow_provider", &pypowsybl::getDefaultLoadFlowProvider, "Get default loadflow provider");

    m.def("get_default_security_analysis_provider", &pypowsybl::getDefaultSecurityAnalysisProvider, "Get default security analysis provider");

    m.def("get_default_sensitivity_analysis_provider", &pypowsybl::getDefaultSensitivityAnalysisProvider, "Get default sensitivity analysis provider");

    m.def("get_version_table", &pypowsybl::getVersionTable, "Get an ASCII table with all PowSybBl modules version");

    m.def("create_network", &pypowsybl::createNetwork, "Create an example network", py::arg("name"), py::arg("id"));

    m.def("update_switch_position", &pypowsybl::updateSwitchPosition, "Update a switch position");

    m.def("merge", &pypowsybl::merge, "Merge several networks");

    m.def("update_connectable_status", &pypowsybl::updateConnectableStatus, "Update a connectable (branch or injection) status");

    py::enum_<element_type>(m, "ElementType")
            .value("BUS", element_type::BUS)
            .value("LINE", element_type::LINE)
            .value("TWO_WINDINGS_TRANSFORMER", element_type::TWO_WINDINGS_TRANSFORMER)
            .value("THREE_WINDINGS_TRANSFORMER", element_type::THREE_WINDINGS_TRANSFORMER)
            .value("GENERATOR", element_type::GENERATOR)
            .value("LOAD", element_type::LOAD)
            .value("BATTERY", element_type::BATTERY)
            .value("SHUNT_COMPENSATOR", element_type::SHUNT_COMPENSATOR)
            .value("NON_LINEAR_SHUNT_COMPENSATOR_SECTION", element_type::NON_LINEAR_SHUNT_COMPENSATOR_SECTION)
            .value("LINEAR_SHUNT_COMPENSATOR_SECTION", element_type::LINEAR_SHUNT_COMPENSATOR_SECTION)
            .value("DANGLING_LINE", element_type::DANGLING_LINE)
            .value("LCC_CONVERTER_STATION", element_type::LCC_CONVERTER_STATION)
            .value("VSC_CONVERTER_STATION", element_type::VSC_CONVERTER_STATION)
            .value("STATIC_VAR_COMPENSATOR", element_type::STATIC_VAR_COMPENSATOR)
            .value("SWITCH", element_type::SWITCH)
            .value("VOLTAGE_LEVEL", element_type::VOLTAGE_LEVEL)
            .value("SUBSTATION", element_type::SUBSTATION)
            .value("BUSBAR_SECTION", element_type::BUSBAR_SECTION)
            .value("HVDC_LINE", element_type::HVDC_LINE)
            .value("RATIO_TAP_CHANGER_STEP", element_type::RATIO_TAP_CHANGER_STEP)
            .value("PHASE_TAP_CHANGER_STEP", element_type::PHASE_TAP_CHANGER_STEP)
            .value("RATIO_TAP_CHANGER", element_type::RATIO_TAP_CHANGER)
            .value("PHASE_TAP_CHANGER", element_type::PHASE_TAP_CHANGER)
            .value("REACTIVE_CAPABILITY_CURVE_POINT", element_type::REACTIVE_CAPABILITY_CURVE_POINT)
            .value("OPERATIONAL_LIMITS", element_type::OPERATIONAL_LIMITS);

    py::enum_<filter_attributes_type>(m, "FilterAttributesType")
            .value("ALL_ATTRIBUTES", filter_attributes_type::ALL_ATTRIBUTES)
            .value("DEFAULT_ATTRIBUTES", filter_attributes_type::DEFAULT_ATTRIBUTES)
            .value("SELECTION_ATTRIBUTES", filter_attributes_type::SELECTION_ATTRIBUTES);

    py::enum_<validation_type>(m, "ValidationType")
            .value("FLOWS", validation_type::FLOWS)
            .value("GENERATORS", validation_type::GENERATORS)
            .value("BUSES", validation_type::BUSES)
            .value("SVCS", validation_type::SVCS)
            .value("SHUNTS", validation_type::SHUNTS)
            .value("TWTS", validation_type::TWTS)
            .value("TWTS3W", validation_type::TWTS3W);

    m.def("get_network_elements_ids", &pypowsybl::getNetworkElementsIds, "Get network elements ids for a given element type",
          py::arg("network"), py::arg("element_type"), py::arg("nominal_voltages"),
          py::arg("countries"), py::arg("main_connected_component"), py::arg("main_synchronous_component"),
          py::arg("not_connected_to_same_bus_at_both_sides"));

    m.def("get_network_import_formats", &pypowsybl::getNetworkImportFormats, "Get supported import formats");
    m.def("get_network_export_formats", &pypowsybl::getNetworkExportFormats, "Get supported export formats");


    m.def("get_loadflow_provider_names", &pypowsybl::getLoadFlowProviderNames, "Get supported loadflow providers");
    m.def("get_security_analysis_provider_names", &pypowsybl::getSecurityAnalysisProviderNames, "Get supported security analysis providers");
    m.def("get_sensitivity_analysis_provider_names", &pypowsybl::getSensitivityAnalysisProviderNames, "Get supported sensitivity analysis providers");

    m.def("create_importer_parameters_series_array", &pypowsybl::createImporterParametersSeriesArray, "Create a parameters series array for a given import format",
          py::arg("format"));

    m.def("create_exporter_parameters_series_array", &pypowsybl::createExporterParametersSeriesArray, "Create a parameters series array for a given export format",
          py::arg("format"));

    m.def("load_network", &pypowsybl::loadNetwork, "Load a network from a file", py::call_guard<py::gil_scoped_release>(),
          py::arg("file"), py::arg("parameters"));

    m.def("load_network_from_string", &pypowsybl::loadNetworkFromString, "Load a network from a string", py::call_guard<py::gil_scoped_release>(),
          py::arg("file_name"), py::arg("file_content"),py::arg("parameters"));

    m.def("dump_network", &pypowsybl::dumpNetwork, "Dump network to a file in a given format", py::call_guard<py::gil_scoped_release>(),
          py::arg("network"), py::arg("file"),py::arg("format"), py::arg("parameters"));

    m.def("dump_network_to_string", &pypowsybl::dumpNetworkToString, "Dump network in a given format", py::call_guard<py::gil_scoped_release>(),
          py::arg("network"), py::arg("format"), py::arg("parameters"));

    m.def("reduce_network", &pypowsybl::reduceNetwork, "Reduce network", py::call_guard<py::gil_scoped_release>(),
          py::arg("network"), py::arg("v_min"), py::arg("v_max"),
          py::arg("ids"), py::arg("vls"), py::arg("depths"), py::arg("with_dangling_lines"));

    py::enum_<pypowsybl::LoadFlowComponentStatus>(m, "LoadFlowComponentStatus", "Loadflow status for one connected component.")
            .value("CONVERGED", pypowsybl::LoadFlowComponentStatus::CONVERGED, "The loadflow has converged.")
            .value("FAILED", pypowsybl::LoadFlowComponentStatus::FAILED, "The loadflow has failed.")
            .value("MAX_ITERATION_REACHED", pypowsybl::LoadFlowComponentStatus::MAX_ITERATION_REACHED, "The loadflow has reached its maximum iterations count.")
            .value("SOLVER_FAILED", pypowsybl::LoadFlowComponentStatus::SOLVER_FAILED, "The loadflow numerical solver has failed.");

    py::class_<load_flow_component_result>(m, "LoadFlowComponentResult", "Loadflow result for one connected component of the network.")
            .def_property_readonly("connected_component_num", [](const load_flow_component_result& r) {
                return r.connected_component_num;
            })
            .def_property_readonly("synchronous_component_num", [](const load_flow_component_result& r) {
                return r.synchronous_component_num;
            })
            .def_property_readonly("status", [](const load_flow_component_result& r) {
                return static_cast<pypowsybl::LoadFlowComponentStatus>(r.status);
            })
            .def_property_readonly("iteration_count", [](const load_flow_component_result& r) {
                return r.iteration_count;
            })
            .def_property_readonly("slack_bus_id", [](const load_flow_component_result& r) {
                return r.slack_bus_id;
            })
            .def_property_readonly("slack_bus_active_power_mismatch", [](const load_flow_component_result& r) {
                return r.slack_bus_active_power_mismatch;
            });

    bindArray<pypowsybl::LoadFlowComponentResultArray>(m, "LoadFlowComponentResultArray");

    py::enum_<pypowsybl::VoltageInitMode>(m, "VoltageInitMode", "Define the computation starting point.")
            .value("UNIFORM_VALUES", pypowsybl::VoltageInitMode::UNIFORM_VALUES, "Initialize voltages to uniform values based on nominale voltage.")
            .value("PREVIOUS_VALUES", pypowsybl::VoltageInitMode::PREVIOUS_VALUES, "Use previously computed voltage values as as starting point.")
            .value("DC_VALUES", pypowsybl::VoltageInitMode::DC_VALUES, "Use values computed by a DC loadflow as a starting point.");

    py::enum_<pypowsybl::BalanceType>(m, "BalanceType", "Define how to distribute slack bus imbalance.")
            .value("PROPORTIONAL_TO_GENERATION_P", pypowsybl::BalanceType::PROPORTIONAL_TO_GENERATION_P,
                   "Distribute slack on generators, in proportion of target P")
            .value("PROPORTIONAL_TO_GENERATION_P_MAX", pypowsybl::BalanceType::PROPORTIONAL_TO_GENERATION_P_MAX,
                   "Distribute slack on generators, in proportion of max P")
            .value("PROPORTIONAL_TO_LOAD", pypowsybl::BalanceType::PROPORTIONAL_TO_LOAD,
                   "Distribute slack on loads, in proportion of load")
            .value("PROPORTIONAL_TO_CONFORM_LOAD", pypowsybl::BalanceType::PROPORTIONAL_TO_CONFORM_LOAD,
                   "Distribute slack on loads, in proportion of conform load");

    py::enum_<pypowsybl::ConnectedComponentMode>(m, "ConnectedComponentMode", "Define which connected components to run on.")
            .value("ALL", pypowsybl::ConnectedComponentMode::ALL, "Run on all connected components")
            .value("MAIN", pypowsybl::ConnectedComponentMode::MAIN, "Run only on the main connected component");
    
    py::class_<array_struct, std::shared_ptr<array_struct>>(m, "ArrayStruct")
            .def(py::init());

    py::class_<dataframe, std::shared_ptr<dataframe>>(m, "Dataframe");

    py::class_<load_flow_parameters, std::shared_ptr<load_flow_parameters>>(m, "LoadFlowParameters")
            .def(py::init(&initLoadFlowParameters))
            .def_property("voltage_init_mode", [](const load_flow_parameters& p) {
                return static_cast<pypowsybl::VoltageInitMode>(p.voltage_init_mode);
            }, [](load_flow_parameters& p, pypowsybl::VoltageInitMode voltageInitMode) {
                p.voltage_init_mode = voltageInitMode;
            })
            .def_property("transformer_voltage_control_on", [](const load_flow_parameters& p) {
                return (bool) p.transformer_voltage_control_on;
            }, [](load_flow_parameters& p, bool transformerVoltageControlOn) {
                p.transformer_voltage_control_on = transformerVoltageControlOn;
            })
            .def_property("no_generator_reactive_limits", [](const load_flow_parameters& p) {
                return (bool) p.no_generator_reactive_limits;
            }, [](load_flow_parameters& p, bool noGeneratorReactiveLimits) {
                p.no_generator_reactive_limits = noGeneratorReactiveLimits;
            })
            .def_property("phase_shifter_regulation_on", [](const load_flow_parameters& p) {
                return (bool) p.phase_shifter_regulation_on;
            }, [](load_flow_parameters& p, bool phaseShifterRegulationOn) {
                p.phase_shifter_regulation_on = phaseShifterRegulationOn;
            })
            .def_property("twt_split_shunt_admittance", [](const load_flow_parameters& p) {
                return (bool) p.twt_split_shunt_admittance;
            }, [](load_flow_parameters& p, bool twtSplitShuntAdmittance) {
                p.twt_split_shunt_admittance = twtSplitShuntAdmittance;
            })
            .def_property("simul_shunt", [](const load_flow_parameters& p) {
                return (bool) p.simul_shunt;
            }, [](load_flow_parameters& p, bool simulShunt) {
                p.simul_shunt = simulShunt;
            })
            .def_property("read_slack_bus", [](const load_flow_parameters& p) {
                return (bool) p.read_slack_bus;
            }, [](load_flow_parameters& p, bool readSlackBus) {
                p.read_slack_bus = readSlackBus;
            })
            .def_property("write_slack_bus", [](const load_flow_parameters& p) {
                return (bool) p.write_slack_bus;
            }, [](load_flow_parameters& p, bool writeSlackBus) {
                p.write_slack_bus = writeSlackBus;
            })
            .def_property("distributed_slack", [](const load_flow_parameters& p) {
                return (bool) p.distributed_slack;
            }, [](load_flow_parameters& p, bool distributedSlack) {
                p.distributed_slack = distributedSlack;
            })
            .def_property("balance_type", [](const load_flow_parameters& p) {
                return static_cast<pypowsybl::BalanceType>(p.balance_type);
            }, [](load_flow_parameters& p, pypowsybl::BalanceType balanceType) {
                p.balance_type = balanceType;
            })
            .def_property("dc_use_transformer_ratio", [](const load_flow_parameters& p) {
                return (bool) p.dc_use_transformer_ratio;
            }, [](load_flow_parameters& p, bool dcUseTransformerRatio) {
                p.dc_use_transformer_ratio = dcUseTransformerRatio;
            })
            .def_property("countries_to_balance", [](const load_flow_parameters& p) {
                return std::vector<std::string>(p.countries_to_balance, p.countries_to_balance + p.countries_to_balance_count);
            }, [](load_flow_parameters& p, const std::vector<std::string>& countriesToBalance) {
                pypowsybl::deleteCharPtrPtr(p.countries_to_balance, p.countries_to_balance_count);
                p.countries_to_balance = pypowsybl::copyVectorStringToCharPtrPtr(countriesToBalance);
                p.countries_to_balance_count = countriesToBalance.size();
            })
            .def_property("connected_component_mode", [](const load_flow_parameters& p) {
                return static_cast<pypowsybl::ConnectedComponentMode>(p.connected_component_mode);
            }, [](load_flow_parameters& p, pypowsybl::ConnectedComponentMode connectedComponentMode) {
                p.connected_component_mode = connectedComponentMode;
            });

    m.def("run_load_flow", &pypowsybl::runLoadFlow, "Run a load flow", py::call_guard<py::gil_scoped_release>(),
          py::arg("network"), py::arg("dc"), py::arg("parameters"), py::arg("provider"));

    m.def("run_load_flow_validation", &pypowsybl::runLoadFlowValidation, "Run a load flow validation", py::arg("network"), py::arg("validation_type"));

    m.def("write_single_line_diagram_svg", &pypowsybl::writeSingleLineDiagramSvg, "Write single line diagram SVG",
          py::arg("network"), py::arg("container_id"), py::arg("svg_file"));

    m.def("get_single_line_diagram_svg", &pypowsybl::getSingleLineDiagramSvg, "Get single line diagram SVG as a string",
          py::arg("network"), py::arg("container_id"));

    m.def("write_network_area_diagram_svg", &pypowsybl::writeNetworkAreaDiagramSvg, "Write network area diagram SVG",
          py::arg("network"), py::arg("svg_file"), py::arg("voltage_level_ids"), py::arg("depth"));

    m.def("get_network_area_diagram_svg", &pypowsybl::getNetworkAreaDiagramSvg, "Get network area diagram SVG as a string",
          py::arg("network"), py::arg("voltage_level_ids"), py::arg("depth"));

    m.def("create_security_analysis", &pypowsybl::createSecurityAnalysis, "Create a security analysis");

    m.def("add_contingency", &pypowsybl::addContingency, "Add a contingency to a security analysis or sensitivity analysis",
          py::arg("analysis_context"), py::arg("contingency_id"), py::arg("elements_ids"));

    py::enum_<pypowsybl::LimitType>(m, "LimitType")
            .value("CURRENT", pypowsybl::LimitType::CURRENT)
            .value("LOW_VOLTAGE", pypowsybl::LimitType::LOW_VOLTAGE)
            .value("HIGH_VOLTAGE", pypowsybl::LimitType::HIGH_VOLTAGE);

    py::enum_<pypowsybl::Side>(m, "Side")
            .value("NONE", pypowsybl::Side::NONE)
            .value("ONE", pypowsybl::Side::ONE)
            .value("TWO", pypowsybl::Side::TWO);

    py::class_<network_metadata, std::shared_ptr<network_metadata>>(m, "NetworkMetadata")
            .def_property_readonly("id", [](const network_metadata& att) {
                return att.id;
            })
            .def_property_readonly("name", [](const network_metadata& att) {
                return att.name;
            })
            .def_property_readonly("source_format", [](const network_metadata& att) {
                return att.source_format;
            })
            .def_property_readonly("forecast_distance", [](const network_metadata& att) {
                return att.forecast_distance;
            })
            .def_property_readonly("case_date", [](const network_metadata& att) {
                return att.case_date;
            });

    py::class_<limit_violation>(m, "LimitViolation")
            .def_property_readonly("subject_id", [](const limit_violation& v) {
                return v.subject_id;
            })
            .def_property_readonly("subject_name", [](const limit_violation& v) {
                return v.subject_name;
            })
            .def_property_readonly("limit_type", [](const limit_violation& v) {
                return static_cast<pypowsybl::LimitType>(v.limit_type);
            })
            .def_property_readonly("limit", [](const limit_violation& v) {
                return v.limit;
            })
            .def_property_readonly("limit_name", [](const limit_violation& v) {
                return v.limit_name;
            })
            .def_property_readonly("acceptable_duration", [](const limit_violation& v) {
                return v.acceptable_duration;
            })
            .def_property_readonly("limit_reduction", [](const limit_violation& v) {
                return v.limit_reduction;
            })
            .def_property_readonly("value", [](const limit_violation& v) {
                return v.value;
            })
            .def_property_readonly("side", [](const limit_violation& v) {
                return static_cast<pypowsybl::Side>(v.side);
            });

    bindArray<pypowsybl::LimitViolationArray>(m, "LimitViolationArray");

    py::class_<contingency_result>(m, "ContingencyResult")
            .def_property_readonly("contingency_id", [](const contingency_result& r) {
                return r.contingency_id;
            })
            .def_property_readonly("status", [](const contingency_result& r) {
                return static_cast<pypowsybl::LoadFlowComponentStatus>(r.status);
            })
            .def_property_readonly("limit_violations", [](const contingency_result& r) {
                return pypowsybl::LimitViolationArray((array *) & r.limit_violations);
            });

    bindArray<pypowsybl::ContingencyResultArray>(m, "ContingencyResultArray");

    m.def("run_security_analysis", &pypowsybl::runSecurityAnalysis, "Run a security analysis", py::call_guard<py::gil_scoped_release>(),
          py::arg("security_analysis_context"), py::arg("network"), py::arg("parameters"),
          py::arg("provider"), py::arg("dc"));

    m.def("create_sensitivity_analysis", &pypowsybl::createSensitivityAnalysis, "Create run_sea sensitivity analysis");

    py::class_<::zone>(m, "Zone")
            .def(py::init([](const std::string& id, const std::vector<std::string>& injectionsIds, const std::vector<double>& injectionsShiftKeys) {
                return pypowsybl::createZone(id, injectionsIds, injectionsShiftKeys);
            }), py::arg("id"), py::arg("injections_ids"), py::arg("injections_shift_keys"));

    m.def("set_zones", &pypowsybl::setZones, "Add zones to sensitivity analysis",
          py::arg("sensitivity_analysis_context"), py::arg("zones"));

    m.def("set_branch_flow_factor_matrix", &pypowsybl::setBranchFlowFactorMatrix, "Add a branch_flow factor matrix to a sensitivity analysis",
          py::arg("sensitivity_analysis_context"), py::arg("branches_ids"), py::arg("variables_ids"));

    m.def("set_bus_voltage_factor_matrix", &pypowsybl::setBusVoltageFactorMatrix, "Add a bus_voltage factor matrix to a sensitivity analysis",
          py::arg("sensitivity_analysis_context"), py::arg("bus_ids"), py::arg("target_voltage_ids"));

    m.def("run_sensitivity_analysis", &pypowsybl::runSensitivityAnalysis, "Run a sensitivity analysis", py::call_guard<py::gil_scoped_release>(),
          py::arg("sensitivity_analysis_context"), py::arg("network"), py::arg("dc"), py::arg("parameters"), py::arg("provider"));

    py::class_<matrix>(m, "Matrix", py::buffer_protocol())
            .def_buffer([](matrix& m) -> py::buffer_info {
                return py::buffer_info(m.values,
                                       sizeof(double),
                                       py::format_descriptor<double>::format(),
                                       2,
                                       { m.row_count, m.column_count },
                                       { sizeof(double) * m.column_count, sizeof(double) });
            });

    m.def("get_branch_flows_sensitivity_matrix", &pypowsybl::getBranchFlowsSensitivityMatrix, "Get sensitivity analysis result matrix for a given contingency",
          py::arg("sensitivity_analysis_result_context"), py::arg("contingency_id"));

    m.def("get_bus_voltages_sensitivity_matrix", &pypowsybl::getBusVoltagesSensitivityMatrix, "Get sensitivity analysis result matrix for a given contingency",
          py::arg("sensitivity_analysis_result_context"), py::arg("contingency_id"));

    m.def("get_reference_flows", &pypowsybl::getReferenceFlows, "Get sensitivity analysis result reference flows for a given contingency",
          py::arg("sensitivity_analysis_result_context"), py::arg("contingency_id"));

    m.def("get_reference_voltages", &pypowsybl::getReferenceVoltages, "Get sensitivity analysis result reference voltages for a given contingency",
          py::arg("sensitivity_analysis_result_context"), py::arg("contingency_id"));

    py::class_<series>(m, "Series")
            .def_property_readonly("name", [](const series& s) {
                return s.name;
            })
            .def_property_readonly("index", [](const series& s) {
                return (bool) s.index;
            })
            .def_property_readonly("data", [](const series& s) -> py::object {
                switch(s.type) {
                    case 0:
                        return py::cast(pypowsybl::toVector<std::string>((array *) & s.data));
                    case 1:
                        return seriesAsNumpyArray<double>(s);
                    case 2:
                        return seriesAsNumpyArray<int>(s);
                    case 3:
                        return seriesAsNumpyArray<bool>(s);
                    default:
                        throw pypowsybl::PyPowsyblError("Series type not supported: " + std::to_string(s.type));
                }
            });
    bindArray<pypowsybl::SeriesArray>(m, "SeriesArray");

    py::class_<pypowsybl::SeriesMetadata>(m, "SeriesMetadata", "Metadata about one series")
            .def(py::init<const std::string&, int, bool, bool, bool>())
            .def_property_readonly("name", &pypowsybl::SeriesMetadata::name, "Name of this series.")
            .def_property_readonly("type", &pypowsybl::SeriesMetadata::type)
            .def_property_readonly("is_index", &pypowsybl::SeriesMetadata::isIndex)
            .def_property_readonly("is_modifiable", &pypowsybl::SeriesMetadata::isModifiable)
            .def_property_readonly("is_default", &pypowsybl::SeriesMetadata::isDefault);

    m.def("get_network_elements_dataframe_metadata", &pypowsybl::getNetworkDataframeMetadata, "Get dataframe metadata for a given network element type",
          py::arg("element_type"));

    m.def("get_network_elements_creation_dataframes_metadata", &pypowsybl::getNetworkElementCreationDataframesMetadata, "Get network elements creation tables metadata",
        py::arg("element_type"));

    m.def("create_network_elements_series_array", &pypowsybl::createNetworkElementsSeriesArray, "Create a network elements series array for a given element type",
          py::call_guard<py::gil_scoped_release>(), py::arg("network"), py::arg("element_type"), py::arg("filter_attributes_type"), py::arg("attributes"), py::arg("array"));
    
    m.def("update_network_elements_with_series", pypowsybl::updateNetworkElementsWithSeries, "Update network elements for a given element type with a series",
          py::call_guard<py::gil_scoped_release>(), py::arg("network"), py::arg("dataframe"), py::arg("element_type"));

    m.def("create_dataframe", ::createDataframe, "create dataframe to update or create new elements", py::arg("columns_values"), py::arg("columns_names"), py::arg("columns_types"), 
          py::arg("is_index"));

    m.def("get_network_metadata", &pypowsybl::getNetworkMetadata, "get attributes", py::arg("network"));
    m.def("get_working_variant_id", &pypowsybl::getWorkingVariantId, "get the current working variant id", py::arg("network"));
    m.def("set_working_variant", &pypowsybl::setWorkingVariant, "set working variant", py::arg("network"), py::arg("variant"));
    m.def("remove_variant", &pypowsybl::removeVariant, "remove a variant", py::arg("network"), py::arg("variant"));
    m.def("clone_variant", &pypowsybl::cloneVariant, "clone a variant", py::arg("network"), py::arg("src"), py::arg("variant"), py::arg("may_overwrite"));
    m.def("get_variant_ids", &pypowsybl::getVariantsIds, "get all variant ids from a network", py::arg("network"));
    m.def("add_monitored_elements", &pypowsybl::addMonitoredElements, "Add monitors to get specific results on network after security analysis process", py::arg("security_analysis_context"),
          py::arg("contingency_context_type"), py::arg("branch_ids"), py::arg("voltage_level_ids"), py::arg("three_windings_transformer_ids"),
          py::arg("contingency_ids"));

    py::enum_<contingency_context_type>(m, "ContingencyContextType")
            .value("ALL", contingency_context_type::ALL)
            .value("NONE", contingency_context_type::NONE)
            .value("SPECIFIC", contingency_context_type::SPECIFIC);

    m.def("get_security_analysis_result", &pypowsybl::getSecurityAnalysisResult, "get result of a security analysis", py::arg("result"));
    m.def("get_node_breaker_view_nodes", &pypowsybl::getNodeBreakerViewNodes, "get all nodes for a voltage level", py::arg("network"), py::arg("voltage_level"));
    m.def("get_node_breaker_view_internal_connections", &pypowsybl::getNodeBreakerViewInternalConnections,
    "get all internal connections for a voltage level", py::arg("network"), py::arg("voltage_level"));
    m.def("get_node_breaker_view_switches", &pypowsybl::getNodeBreakerViewSwitches, "get all switches for a voltage level in bus breaker view", py::arg("network"), py::arg("voltage_level"));
    m.def("get_bus_breaker_view_elements", &pypowsybl::getBusBreakerViewElements, "get all elements for a voltage level in bus breaker view", py::arg("network"), py::arg("voltage_level"));
    m.def("get_bus_breaker_view_buses", &pypowsybl::getBusBreakerViewBuses,
    "get all buses for a voltage level in bus breaker view", py::arg("network"), py::arg("voltage_level"));
    m.def("get_bus_breaker_view_switches", &pypowsybl::getBusBreakerViewSwitches, "get all switches for a voltage level", py::arg("network"), py::arg("voltage_level"));
    m.def("get_limit_violations", &pypowsybl::getLimitViolations, "get limit violations of a security analysis", py::arg("result"));

    m.def("get_branch_results", &pypowsybl::getBranchResults, "create a table with all branch results computed after security analysis",
          py::arg("result"));
    m.def("get_bus_results", &pypowsybl::getBusResults, "create a table with all bus results computed after security analysis",
          py::arg("result"));
    m.def("get_three_windings_transformer_results", &pypowsybl::getThreeWindingsTransformerResults,
          "create a table with all three windings transformer results computed after security analysis", py::arg("result"));
    m.def("create_element", ::createElement, "create a new element on the network", py::arg("network"),  py::arg("dataframes"),  py::arg("elementType"));
}
