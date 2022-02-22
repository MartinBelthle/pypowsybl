/**
 * Copyright (c) 2021, RTE (http://www.rte-france.com)
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.powsybl.python;

import com.powsybl.dataframe.DataframeFilter;
import com.powsybl.dataframe.DataframeMapper;
import com.powsybl.dataframe.DataframeMapperBuilder;
import com.powsybl.dataframe.impl.DefaultDataframeHandler;
import com.powsybl.dataframe.impl.Series;
import com.powsybl.iidm.export.Exporter;
import com.powsybl.iidm.import_.Importer;
import com.powsybl.iidm.network.*;
import com.powsybl.iidm.parameters.Parameter;
import com.powsybl.python.PyPowsyblApiHeader.ArrayPointer;
import com.powsybl.python.PyPowsyblApiHeader.SeriesPointer;
import com.powsybl.security.LimitViolation;
import com.powsybl.security.SecurityAnalysisResult;
import org.apache.commons.collections4.IteratorUtils;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Mappers to dataframes.
 *
 * @author Sylvain Leclerc <sylvain.leclerc at rte-france.com>
 */
public final class Dataframes {

    private static final DataframeMapper<Importer> IMPORTER_PARAMETERS_MAPPER = new DataframeMapperBuilder<Importer, Parameter>()
            .itemsProvider(Importer::getParameters)
            .stringsIndex("name", Parameter::getName)
            .strings("description", Parameter::getDescription)
            .strings("type", p -> p.getType().toString())
            .strings("default", p -> Objects.toString(p.getDefaultValue(), ""))
            .build();

    private static final DataframeMapper<Exporter> EXPORTER_PARAMETERS_MAPPER = new DataframeMapperBuilder<Exporter, Parameter>()
            .itemsProvider(Exporter::getParameters)
            .stringsIndex("name", Parameter::getName)
            .strings("description", Parameter::getDescription)
            .strings("type", p -> p.getType().toString())
            .strings("default", p -> Objects.toString(p.getDefaultValue(), ""))
            .build();

    private static final DataframeMapper<SecurityAnalysisResult> BRANCH_RESULTS_MAPPER = createBranchResultsMapper();
    private static final DataframeMapper<SecurityAnalysisResult> T3WT_RESULTS_MAPPER = createThreeWindingsTransformersResults();
    private static final DataframeMapper<SecurityAnalysisResult> BUS_RESULTS_MAPPER = createBusResultsMapper();
    private static final DataframeMapper<SecurityAnalysisResult> LIMIT_VIOLATIONS_MAPPER = createLimitViolationsMapper();
    private static final DataframeMapper<VoltageLevel.NodeBreakerView> NODE_BREAKER_VIEW_SWITCHES_MAPPER = createNodeBreakerViewSwitchesMapper();
    private static final DataframeMapper<VoltageLevel.NodeBreakerView> NODE_BREAKER_VIEW_NODES_MAPPER = createNodeBreakerViewNodes();
    private static final DataframeMapper<VoltageLevel.NodeBreakerView> NODE_BREAKER_VIEW_INTERNAL_CONNECTION_MAPPER = createNodeBreakerViewInternalConnections();
    private static final DataframeMapper<VoltageLevel.BusBreakerView> BUS_BREAKER_VIEW_SWITCHES_MAPPER = createBusBreakerViewSwitchesMapper();
    private static final DataframeMapper<VoltageLevel> BUS_BREAKER_VIEW_BUSES_MAPPER = createBusBreakerViewBuses();
    private static final DataframeMapper<VoltageLevel> BUS_BREAKER_VIEW_ELEMENTS_MAPPER = createBusBreakerViewElements();

    private Dataframes() {
    }

    /**
     * Maps an object to a C struct using the provided mapper.
     */
    public static <T> ArrayPointer<SeriesPointer> createCDataframe(DataframeMapper<T> mapper, T object) {
        return createCDataframe(mapper, object, new DataframeFilter());
    }

    public static <T> ArrayPointer<SeriesPointer> createCDataframe(DataframeMapper<T> mapper, T object, DataframeFilter dataframeFilter) {
        CDataframeHandler handler = new CDataframeHandler();
        mapper.createDataframe(object, handler, dataframeFilter);
        return handler.getDataframePtr();
    }

    /**
     * Maps an object to java series
     */
    public static <T> List<Series> createSeries(DataframeMapper<T> mapper, T object) {
        List<Series> series = new ArrayList<>();
        mapper.createDataframe(object, new DefaultDataframeHandler(series::add), new DataframeFilter());
        return List.copyOf(series);
    }

    /**
     * A mapper which maps an importer to a dataframe containing its parameters.
     */
    static DataframeMapper<Importer> importerParametersMapper() {
        return IMPORTER_PARAMETERS_MAPPER;
    }

    static DataframeMapper<Exporter> exporterParametersMapper() {
        return EXPORTER_PARAMETERS_MAPPER;
    }

    public static DataframeMapper<SecurityAnalysisResult> branchResultsMapper() {
        return BRANCH_RESULTS_MAPPER;
    }

    public static DataframeMapper<SecurityAnalysisResult> busResultsMapper() {
        return BUS_RESULTS_MAPPER;
    }

    public static DataframeMapper<SecurityAnalysisResult> threeWindingsTransformerResultsMapper() {
        return T3WT_RESULTS_MAPPER;
    }

    public static DataframeMapper<SecurityAnalysisResult> limitViolationsMapper() {
        return LIMIT_VIOLATIONS_MAPPER;
    }

    public static DataframeMapper<VoltageLevel.NodeBreakerView> nodeBreakerViewSwitches() {
        return NODE_BREAKER_VIEW_SWITCHES_MAPPER;
    }

    public static DataframeMapper<VoltageLevel.NodeBreakerView> nodeBreakerViewNodes() {
        return NODE_BREAKER_VIEW_NODES_MAPPER;
    }

    public static DataframeMapper<VoltageLevel.NodeBreakerView> nodeBreakerViewInternalConnection() {
        return NODE_BREAKER_VIEW_INTERNAL_CONNECTION_MAPPER;
    }

    public static DataframeMapper<VoltageLevel.BusBreakerView> busBreakerViewSwitches() {
        return BUS_BREAKER_VIEW_SWITCHES_MAPPER;
    }

    public static DataframeMapper<VoltageLevel> busBreakerViewBuses() {
        return BUS_BREAKER_VIEW_BUSES_MAPPER;
    }

    public static DataframeMapper<VoltageLevel> busBreakerViewElements() {
        return BUS_BREAKER_VIEW_ELEMENTS_MAPPER;
    }

    private static List<BranchResultContext> getBranchResults(SecurityAnalysisResult result) {
        List<BranchResultContext> branchResults = result.getPreContingencyResult()
                .getPreContingencyBranchResults().stream()
                .map(branchResult -> new BranchResultContext(branchResult, null))
                .collect(Collectors.toList());
        result.getPostContingencyResults().forEach(postContingencyResult -> {
            postContingencyResult.getBranchResults()
                    .forEach(branchResult -> branchResults.add(new BranchResultContext(branchResult, postContingencyResult.getContingency().getId())));
        });
        return branchResults;
    }

    private static DataframeMapper<SecurityAnalysisResult> createBranchResultsMapper() {
        return new DataframeMapperBuilder<SecurityAnalysisResult, BranchResultContext>()
                .itemsProvider(Dataframes::getBranchResults)
                .stringsIndex("contingency_id", BranchResultContext::getContingencyId)
                .stringsIndex("branch_id", BranchResultContext::getBranchId)
                .doubles("p1", BranchResultContext::getP1)
                .doubles("q1", BranchResultContext::getQ1)
                .doubles("i1", BranchResultContext::getI1)
                .doubles("p2", BranchResultContext::getP2)
                .doubles("q2", BranchResultContext::getQ2)
                .doubles("i2", BranchResultContext::getI2)
                .build();
    }

    private static List<BusResultContext> getBusResults(SecurityAnalysisResult result) {
        List<BusResultContext> busResults = result.getPreContingencyResult()
                .getPreContingencyBusResults().stream()
                .map(busResult -> new BusResultContext(busResult, null))
                .collect(Collectors.toList());
        result.getPostContingencyResults().forEach(postContingencyResult -> {
            postContingencyResult.getBusResults()
                    .forEach(busResult -> busResults.add(new BusResultContext(busResult, postContingencyResult.getContingency().getId())));
        });
        return busResults;
    }

    private static DataframeMapper<SecurityAnalysisResult> createBusResultsMapper() {
        return new DataframeMapperBuilder<SecurityAnalysisResult, BusResultContext>()
                .itemsProvider(Dataframes::getBusResults)
                .stringsIndex("contingency_id", BusResultContext::getContingencyId)
                .stringsIndex("voltage_level_id", BusResultContext::getVoltageLevelId)
                .stringsIndex("bus_id", BusResultContext::getBusId)
                .doubles("v_mag", BusResultContext::getV)
                .doubles("v_angle", BusResultContext::getAngle)
                .build();
    }

    private static List<ThreeWindingsTransformerResultContext> getThreeWindingsTransformerResults(SecurityAnalysisResult result) {
        List<ThreeWindingsTransformerResultContext> threeWindingsTransformerResults = result.getPreContingencyResult()
                .getPreContingencyThreeWindingsTransformerResults().stream()
                .map(threeWindingsTransformerResult -> new ThreeWindingsTransformerResultContext(threeWindingsTransformerResult, null))
                .collect(Collectors.toList());
        result.getPostContingencyResults().forEach(postContingencyResult -> {
            postContingencyResult.getThreeWindingsTransformerResult()
                    .forEach(threeWindingsTransformerResult ->
                            threeWindingsTransformerResults.add(new ThreeWindingsTransformerResultContext(threeWindingsTransformerResult,
                                    postContingencyResult.getContingency().getId())));
        });
        return threeWindingsTransformerResults;
    }

    private static DataframeMapper<SecurityAnalysisResult> createThreeWindingsTransformersResults() {
        return new DataframeMapperBuilder<SecurityAnalysisResult, ThreeWindingsTransformerResultContext>()
                .itemsProvider(Dataframes::getThreeWindingsTransformerResults)
                .stringsIndex("contingency_id", ThreeWindingsTransformerResultContext::getContingencyId)
                .stringsIndex("transformer_id", ThreeWindingsTransformerResultContext::getThreeWindingsTransformerId)
                .doubles("p1", ThreeWindingsTransformerResultContext::getP1)
                .doubles("q1", ThreeWindingsTransformerResultContext::getQ1)
                .doubles("i1", ThreeWindingsTransformerResultContext::getI1)
                .doubles("p2", ThreeWindingsTransformerResultContext::getP2)
                .doubles("q2", ThreeWindingsTransformerResultContext::getQ2)
                .doubles("i2", ThreeWindingsTransformerResultContext::getI2)
                .doubles("p3", ThreeWindingsTransformerResultContext::getP3)
                .doubles("q3", ThreeWindingsTransformerResultContext::getQ3)
                .doubles("i3", ThreeWindingsTransformerResultContext::getI3)
                .build();
    }

    private static List<LimitViolationContext> getLimitViolations(SecurityAnalysisResult result) {
        List<LimitViolationContext> limitViolations = result.getPreContingencyResult().getLimitViolationsResult().getLimitViolations()
                .stream().map(limitViolation -> new LimitViolationContext("", limitViolation)).collect(Collectors.toList());
        result.getPostContingencyResults()
                .forEach(postContingencyResult -> limitViolations.addAll(postContingencyResult.getLimitViolationsResult()
                        .getLimitViolations().stream()
                        .map(limitViolation -> new LimitViolationContext(postContingencyResult.getContingency().getId(), limitViolation))
                        .collect(Collectors.toList())));
        return limitViolations;
    }

    private static DataframeMapper<SecurityAnalysisResult> createLimitViolationsMapper() {
        return new DataframeMapperBuilder<SecurityAnalysisResult, LimitViolationContext>()
                .itemsProvider(Dataframes::getLimitViolations)
                .stringsIndex("contingency_id", LimitViolationContext::getContingencyId)
                .stringsIndex("subject_id", LimitViolation::getSubjectId)
                .strings("subject_name", p -> Objects.toString(p.getSubjectName(), ""))
                .strings("limit_type", l -> l.getLimitType().toString())
                .strings("limit_name", p -> Objects.toString(p.getLimitName(), ""))
                .doubles("limit", LimitViolation::getLimit)
                .ints("acceptable_duration", LimitViolation::getAcceptableDuration)
                .doubles("limit_reduction", LimitViolation::getLimitReduction)
                .doubles("value", LimitViolation::getValue)
                .strings("side", p -> Objects.toString(p.getSide(), ""))
                .build();
    }

    private static List<NodeBreakerViewSwitchContext> getNodeBreakerViewSwitches(VoltageLevel.NodeBreakerView nodeBreakerView) {
        return IteratorUtils.toList(nodeBreakerView.getSwitches().iterator()).stream().map(switchContext ->
                new NodeBreakerViewSwitchContext(switchContext,
                        nodeBreakerView.getNode1(switchContext.getId()),
                        nodeBreakerView.getNode2(switchContext.getId())))
                .collect(Collectors.toList());
    }

    private static DataframeMapper<VoltageLevel.NodeBreakerView> createNodeBreakerViewSwitchesMapper() {
        return new DataframeMapperBuilder<VoltageLevel.NodeBreakerView, NodeBreakerViewSwitchContext>()
                .itemsProvider(Dataframes::getNodeBreakerViewSwitches)
                .stringsIndex("id", nodeBreakerViewSwitchContext -> nodeBreakerViewSwitchContext.getSwitchContext().getId())
                .strings("name", nodeBreakerViewSwitchContext -> nodeBreakerViewSwitchContext.getSwitchContext().getOptionalName().orElse(""))
                .strings("kind", nodeBreakerViewSwitchContext -> nodeBreakerViewSwitchContext.getSwitchContext().getKind().toString())
                .booleans("open", nodeBreakerViewSwitchContext -> nodeBreakerViewSwitchContext.getSwitchContext().isOpen())
                .booleans("retained", nodeBreakerViewSwitchContext -> nodeBreakerViewSwitchContext.getSwitchContext().isRetained())
                .ints("node1", NodeBreakerViewSwitchContext::getNode1)
                .ints("node2", NodeBreakerViewSwitchContext::getNode2)
                .build();
    }

    private static List<NodeContext> getNodeBreakerViewNodes(VoltageLevel.NodeBreakerView nodeBreakerView) {
        List<Integer> nodes = Arrays.stream(nodeBreakerView.getNodes()).boxed().collect(Collectors.toList());
        return nodes.stream().map(node -> {
            Terminal terminal = nodeBreakerView.getTerminal(node);
            if (terminal == null) {
                return new NodeContext(node, null);
            } else {
                return new NodeContext(node, terminal.getConnectable().getId());
            }
        }).collect(Collectors.toList());
    }

    private static DataframeMapper<VoltageLevel.NodeBreakerView> createNodeBreakerViewNodes() {
        return new DataframeMapperBuilder<VoltageLevel.NodeBreakerView, NodeContext>()
                .itemsProvider(Dataframes::getNodeBreakerViewNodes)
                .intsIndex("node", NodeContext::getNode)
                .strings("connectable_id", node -> Objects.toString(node.getConnectableId(), ""))
                .build();
    }

    private static List<InternalConnectionContext> getNodeBreakerViewInternalConnections(VoltageLevel.NodeBreakerView nodeBreakerView) {
        List<VoltageLevel.NodeBreakerView.InternalConnection> internalConnectionContextList = IteratorUtils
                .toList(nodeBreakerView.getInternalConnections().iterator());
        return internalConnectionContextList.stream()
                .map(internalConnection ->
                        new InternalConnectionContext(internalConnection, internalConnectionContextList.indexOf(internalConnection)))
                .collect(Collectors.toList());
    }

    private static DataframeMapper<VoltageLevel.NodeBreakerView> createNodeBreakerViewInternalConnections() {
        return new DataframeMapperBuilder<VoltageLevel.NodeBreakerView, InternalConnectionContext>()
                .itemsProvider(Dataframes::getNodeBreakerViewInternalConnections)
                .intsIndex("id", InternalConnectionContext::getIndex)
                .ints("node1", internalConnectionContext -> internalConnectionContext.getInternalConnection().getNode1())
                .ints("node2", internalConnectionContext -> internalConnectionContext.getInternalConnection().getNode2())
                .build();
    }

    private static List<BusBreakerViewSwitchContext> getBusBreakerViewSwitches(VoltageLevel.BusBreakerView busBreakerView) {
        return IteratorUtils.toList(busBreakerView.getSwitches().iterator()).
                stream()
                .map(switchDevice -> new BusBreakerViewSwitchContext(switchDevice,
                        busBreakerView.getBus1(switchDevice.getId()).getId(), busBreakerView.getBus2(switchDevice.getId()).getId()))
                .collect(Collectors.toList());
    }

    private static DataframeMapper<VoltageLevel.BusBreakerView> createBusBreakerViewSwitchesMapper() {
        return new DataframeMapperBuilder<VoltageLevel.BusBreakerView, BusBreakerViewSwitchContext>()
                .itemsProvider(Dataframes::getBusBreakerViewSwitches)
                .stringsIndex("id", context -> context.getSwitchContext().getId())
                .strings("kind", context -> context.getSwitchContext().getKind().toString())
                .booleans("open", context -> context.getSwitchContext().isOpen())
                .strings("bus1_id", BusBreakerViewSwitchContext::getBusId1)
                .strings("bus2_id", BusBreakerViewSwitchContext::getBusId2)
                .build();
    }

    private static List<BusBreakerViewBusContext> getBusBreakerViewBuses(VoltageLevel voltageLevel) {
        return voltageLevel.getBusBreakerView().getBusStream().map(bus -> {
            Terminal terminal = bus.getConnectedTerminalStream().collect(Collectors.toList()).get(0);
            Bus busViewBus = terminal.getBusView().getBus();
            return new BusBreakerViewBusContext(bus, busViewBus);
        }).collect(Collectors.toList());

    }

    private static DataframeMapper<VoltageLevel> createBusBreakerViewBuses() {
        return new DataframeMapperBuilder<VoltageLevel, BusBreakerViewBusContext>()
                .itemsProvider(Dataframes::getBusBreakerViewBuses)
                .stringsIndex("id", busContext -> busContext.getBusBreakerViewBus().getId())
                .strings("name", busContext -> busContext.getBusBreakerViewBus()
                        .getOptionalName().orElse(""))
                .strings("bus_id", busContext -> busContext.getBusViewBus().getId())
                .build();
    }

    private static List<BusBreakerViewElementContext> getBusBreakerViewElements(VoltageLevel voltageLevel) {
        List<BusBreakerViewElementContext> result = new ArrayList<>();
        voltageLevel.getConnectableStream().forEach(connectable -> {
            if (connectable instanceof Injection) {
                Injection<?> inj = (Injection<?>) connectable;
                result.add(new BusBreakerViewElementContext(connectable.getType(),
                        inj.getTerminal().getBusBreakerView().getBus().getId(), connectable.getId()));
            } else if (connectable instanceof Branch) {
                Branch<?> branch = (Branch<?>) connectable;
                if (branch.getTerminal1().getVoltageLevel() == voltageLevel) {
                    result.add(new BusBreakerViewElementContext(connectable.getType(),
                            branch.getTerminal1().getBusBreakerView().getBus().getId(), connectable.getId(), SideEnum.ONE));
                }
                if (branch.getTerminal2().getVoltageLevel() == voltageLevel) {
                    result.add(new BusBreakerViewElementContext(connectable.getType(),
                            branch.getTerminal2().getBusBreakerView().getBus().getId(), connectable.getId(), SideEnum.TWO));
                }
            } else if (connectable instanceof ThreeWindingsTransformer) {
                ThreeWindingsTransformer transfo = (ThreeWindingsTransformer) connectable;
                if (transfo.getLeg1().getTerminal().getVoltageLevel() == voltageLevel) {
                    result.add(new BusBreakerViewElementContext(connectable.getType(),
                            transfo.getLeg1().getTerminal().getBusBreakerView().getBus().getId(), transfo.getId(), SideEnum.ONE));
                }
                if (transfo.getLeg2().getTerminal().getVoltageLevel() == voltageLevel) {
                    result.add(new BusBreakerViewElementContext(connectable.getType(),
                            transfo.getLeg2().getTerminal().getBusBreakerView().getBus().getId(), transfo.getId(), SideEnum.TWO));
                }
                if (transfo.getLeg3().getTerminal().getVoltageLevel() == voltageLevel) {
                    result.add(new BusBreakerViewElementContext(connectable.getType(),
                            transfo.getLeg3().getTerminal().getBusBreakerView().getBus().getId(), transfo.getId(), SideEnum.THREE));
                }
            }
        });
        return result;
    }

    private static DataframeMapper<VoltageLevel> createBusBreakerViewElements() {
        return new DataframeMapperBuilder<VoltageLevel, BusBreakerViewElementContext>()
                .itemsProvider(Dataframes::getBusBreakerViewElements)
                .stringsIndex("id", BusBreakerViewElementContext::getElementId)
                .strings("type", elementContext -> elementContext.getType().toString())
                .strings("bus_id", BusBreakerViewElementContext::getBusId)
                .strings("side", elementContext -> elementContext.getSide().isPresent() ? elementContext.getSide().get().toString() : "")
                .build();
    }
}
