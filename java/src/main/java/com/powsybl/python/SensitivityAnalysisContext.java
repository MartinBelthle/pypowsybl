/**
 * Copyright (c) 2021, RTE (http://www.rte-france.com)
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.powsybl.python;

import com.powsybl.commons.PowsyblException;
import com.powsybl.commons.reporter.Reporter;
import com.powsybl.computation.local.LocalComputationManager;
import com.powsybl.contingency.Contingency;
import com.powsybl.contingency.ContingencyContext;
import com.powsybl.iidm.network.Branch;
import com.powsybl.iidm.network.Injection;
import com.powsybl.iidm.network.Network;
import com.powsybl.iidm.network.TwoWindingsTransformer;
import com.powsybl.contingency.ContingencyContextType;
import com.powsybl.loadflow.LoadFlowParameters;
import com.powsybl.sensitivity.*;

import java.util.*;
import java.util.stream.Collectors;

/**
 * @author Geoffroy Jamgotchian {@literal <geoffroy.jamgotchian at rte-france.com>}
 */
class SensitivityAnalysisContext extends AbstractContingencyContainer {

    private List<SensitivityVariableSet> variableSets = Collections.emptyList();

    class MatrixInfo {
        ContingencyContextType contingencyContextType;

        SensitivityFunctionType functionType;

        private List<String> columnIds;

        private List<String> rowIds;

        private List<String> contingencyIds;

        int offsetData;

        int offsetColumn;

        MatrixInfo(ContingencyContextType context, SensitivityFunctionType functionType, List<String> columnIds, List<String> rowIds, List<String> contingencyIds) {
            this.contingencyContextType = context;
            this.functionType = functionType;
            this.columnIds = columnIds;
            this.rowIds = rowIds;
            this.contingencyIds = contingencyIds;
        }

        ContingencyContextType getContingencyContextType() {
            return contingencyContextType;
        }

        SensitivityFunctionType getFunctionType() {
            return functionType;
        }

        void setOffsetData(int offset) {
            this.offsetData = offset;
        }

        void setOffsetColumn(int offset) {
            this.offsetColumn = offset;
        }

        int getOffsetData() {
            return offsetData;
        }

        int getOffsetColumn() {
            return offsetColumn;
        }

        List<String> getRowIds() {
            return rowIds;
        }

        List<String> getColumnIds() {
            return columnIds;
        }

        List<String> getContingencyIds() {
            return contingencyIds;
        }

        int getRowCount() {
            return rowIds.size();
        }

        int getColumnCount() {
            return columnIds.size();
        }
    }

    Map<String, MatrixInfo> branchFlowFactorsMatrix = new HashMap<>();

    MatrixInfo busVoltageFactorsMatrix = null;

    Map<String, MatrixInfo> preContingencyFactorMatrix = new HashMap<>();

    Map<String, MatrixInfo> postContingencyFactorMatrix = new HashMap<>();

    void setBranchFlowFactorMatrix(List<String> branchesIds, List<String> variablesIds) {
        addBranchFlowFactorMatrix("default", branchesIds, variablesIds);
    }

    void addBranchFlowFactorMatrix(String matrixId, List<String> branchesIds, List<String> variablesIds) {
        MatrixInfo info = new MatrixInfo(ContingencyContextType.ALL, SensitivityFunctionType.BRANCH_ACTIVE_POWER, branchesIds, variablesIds, Collections.emptyList());
        branchFlowFactorsMatrix.put(matrixId, info);
    }

    void addPreContingencyBranchFlowFactorMatrix(String matrixId, List<String> branchesIds, List<String> variablesIds) {
        MatrixInfo info = new MatrixInfo(ContingencyContextType.NONE, SensitivityFunctionType.BRANCH_ACTIVE_POWER, branchesIds, variablesIds, Collections.emptyList());
        preContingencyFactorMatrix.put(matrixId, info);
    }

    void addPostContingencyBranchFlowFactorMatrix(String matrixId, List<String> branchesIds, List<String> variablesIds, List<String> contingencies) {
        MatrixInfo info = new MatrixInfo(ContingencyContextType.SPECIFIC, SensitivityFunctionType.BRANCH_ACTIVE_POWER, branchesIds, variablesIds, contingencies);
        postContingencyFactorMatrix.put(matrixId, info);
    }

    public void setVariableSets(List<SensitivityVariableSet> variableSets) {
        this.variableSets = Objects.requireNonNull(variableSets);
    }

    void setBusVoltageFactorMatrix(List<String> busVoltageIds, List<String> targetVoltageIds) {
        this.busVoltageFactorsMatrix = new MatrixInfo(ContingencyContextType.ALL, SensitivityFunctionType.BUS_VOLTAGE, busVoltageIds, targetVoltageIds, Collections.emptyList());
    }

    private static Injection<?> getInjection(Network network, String injectionId) {
        Injection<?> injection = network.getGenerator(injectionId);
        if (injection == null) {
            injection = network.getLoad(injectionId);
        }
        if (injection == null) {
            injection = network.getLccConverterStation(injectionId);
        }
        if (injection == null) {
            injection = network.getVscConverterStation(injectionId);
        }
        return injection;
    }

    List<MatrixInfo> prepareMatrices() {
        List<MatrixInfo> matrices = new ArrayList<>();
        int offsetData = 0;
        int offsetColumns = 0;

        for (MatrixInfo matrix : branchFlowFactorsMatrix.values()) {
            matrix.setOffsetData(offsetData);
            matrix.setOffsetColumn(offsetColumns);
            matrices.add(matrix);
            offsetData += matrix.getColumnCount() * matrix.getRowCount();
            offsetColumns += matrix.getColumnCount();
        }

        for (MatrixInfo matrix : preContingencyFactorMatrix.values()) {
            matrix.setOffsetData(offsetData);
            matrix.setOffsetColumn(offsetColumns);
            matrices.add(matrix);
            offsetData += matrix.getColumnCount() * matrix.getRowCount();
            offsetColumns += matrix.getColumnCount();
        }

        for (MatrixInfo matrix : postContingencyFactorMatrix.values()) {
            matrix.setOffsetData(offsetData);
            matrix.setOffsetColumn(offsetColumns);
            matrices.add(matrix);
            offsetData += matrix.getColumnCount() * matrix.getRowCount();
            offsetColumns += matrix.getColumnCount();
        }

        if (busVoltageFactorsMatrix != null) {
            busVoltageFactorsMatrix.setOffsetData(offsetData);
            busVoltageFactorsMatrix.setOffsetColumn(offsetColumns);
            matrices.add(busVoltageFactorsMatrix);
        }
        return matrices;
    }

    int getTotalNumberOfMatrixFactors(List<MatrixInfo> matrices) {
        int count = 0;
        for (MatrixInfo matrix : matrices) {
            count += matrix.getColumnCount() * matrix.getRowCount();
        }
        return count;
    }

    int getTotalNumberOfMatrixFactorsColumns(List<MatrixInfo> matrices) {
        int count = 0;
        for (MatrixInfo matrix : matrices) {
            count += matrix.getColumnCount();
        }
        return count;
    }

    SensitivityAnalysisResultContext run(Network network, LoadFlowParameters loadFlowParameters, String provider) {
            SensitivityAnalysisParameters sensitivityAnalysisParameters = PyPowsyblConfiguration.isReadConfig() ? SensitivityAnalysisParameters.load() : new SensitivityAnalysisParameters();
        sensitivityAnalysisParameters.setLoadFlowParameters(loadFlowParameters);
        List<Contingency> contingencies = createContingencies(network);

        List<MatrixInfo> matrices = prepareMatrices();

        Map<String, SensitivityVariableSet> variableSetsById = variableSets.stream().collect(Collectors.toMap(SensitivityVariableSet::getId, e -> e));

        SensitivityFactorReader factorReader = handler -> {

            for (MatrixInfo matrix : matrices) {
                List<String> columns = matrix.getColumnIds();
                List<String> rows = matrix.getRowIds();
                List<ContingencyContext> contingencyContexts = new ArrayList<>();
                if (matrix.getContingencyContextType() == ContingencyContextType.ALL) {
                    contingencyContexts.add(ContingencyContext.all());
                } else if (matrix.getContingencyContextType() == ContingencyContextType.NONE) {
                    contingencyContexts.add(ContingencyContext.none());
                } else {
                    for (String c : matrix.getContingencyIds()) {
                        contingencyContexts.add(ContingencyContext.specificContingency(c));
                    }
                }

                if (matrix.getFunctionType() == SensitivityFunctionType.BRANCH_ACTIVE_POWER) {
                    for (int row = 0; row < rows.size(); row++) {
                        String variableId = rows.get(row);
                        Injection<?> injection = getInjection(network, variableId);
                        for (int column = 0; column < columns.size(); column++) {
                            int index = matrix.getOffsetData() + column + columns.size() * row;
                            String branchId = columns.get(column);
                            Branch branch = network.getBranch(branchId);
                            if (branch == null) {
                                throw new PowsyblException("Branch '" + branchId + "' not found");
                            }
                            if (injection != null) {
                                for (ContingencyContext cCtx : contingencyContexts) {
                                    handler.onFactor(SensitivityFunctionType.BRANCH_ACTIVE_POWER, branchId,
                                            SensitivityVariableType.INJECTION_ACTIVE_POWER, variableId,
                                            false, cCtx);
                                }
                            } else {
                                TwoWindingsTransformer twt = network.getTwoWindingsTransformer(variableId);
                                if (twt != null) {
                                    if (twt.getPhaseTapChanger() == null) {
                                        throw new PowsyblException("Transformer '" + variableId + "' is not a phase shifter");
                                    }
                                    for (ContingencyContext cCtx : contingencyContexts) {
                                        handler.onFactor(SensitivityFunctionType.BRANCH_ACTIVE_POWER, branchId,
                                                SensitivityVariableType.TRANSFORMER_PHASE, variableId,
                                                false, cCtx);
                                    }
                                } else {
                                    if (variableSetsById.containsKey(variableId)) {
                                        for (ContingencyContext cCtx : contingencyContexts) {
                                            handler.onFactor(SensitivityFunctionType.BRANCH_ACTIVE_POWER, branchId,
                                                    SensitivityVariableType.INJECTION_ACTIVE_POWER, variableId,
                                                    true, cCtx);
                                        }
                                    } else {
                                        throw new PowsyblException("Variable '" + variableId + "' not found");
                                    }
                                }
                            }
                        }
                    }
                } else if (matrix.getFunctionType() == SensitivityFunctionType.BUS_VOLTAGE) {
                    for (int row = 0; row < rows.size(); row++) {
                        final String targetVoltageId = rows.get(row);
                        for (int column = 0; column < columns.size(); column++) {
                            int index = matrix.getOffsetData() + column + rows.size() * row;
                            final String busVoltageId = columns.get(column);
                            handler.onFactor(SensitivityFunctionType.BUS_VOLTAGE, busVoltageId,
                                    SensitivityVariableType.BUS_TARGET_VOLTAGE, targetVoltageId, false, ContingencyContext.all());
                        }
                    }
                }
            }
        };

        int baseCaseValueSize = getTotalNumberOfMatrixFactors(matrices);
        double[] baseCaseValues = new double[baseCaseValueSize];
        double[][] valuesByContingencyIndex = new double[contingencies.size()][baseCaseValueSize];

        int totalColumnsCount = getTotalNumberOfMatrixFactorsColumns(matrices);
        double[] baseCaseReferences = new double[totalColumnsCount];
        double[][] referencesByContingencyIndex = new double[contingencies.size()][totalColumnsCount];

        NavigableMap<Integer, MatrixInfo> factorIndexMatrixMap = new TreeMap<>();
        NavigableMap<Integer, MatrixInfo> columnsIndexMatrixMap = new TreeMap<>();
        for (MatrixInfo m : matrices) {
            factorIndexMatrixMap.put(m.getOffsetData(), m);
            columnsIndexMatrixMap.put(m.getOffsetColumn(), m);
        }

        SensitivityValueWriter valueWriter = (factorContext, contingencyIndex, value, functionReference) -> {
            int factorIndex = (Integer) factorContext;
            MatrixInfo m = factorIndexMatrixMap.floorEntry(factorIndex).getValue();

            int columnIdx = m.getOffsetColumn() + (factorIndex - m.getOffsetData()) % m.getColumnCount();
            if (contingencyIndex != -1) {
                valuesByContingencyIndex[contingencyIndex][factorIndex] = value;
                referencesByContingencyIndex[contingencyIndex][columnIdx] = functionReference;
            } else {
                baseCaseValues[factorIndex] = value;
                baseCaseReferences[columnIdx] = functionReference;
            }
        };

        SensitivityAnalysis.find(provider)
                .run(network,
                        network.getVariantManager().getWorkingVariantId(),
                        factorReader,
                        valueWriter,
                        contingencies,
                        variableSets,
                        sensitivityAnalysisParameters,
                        LocalComputationManager.getDefault(),
                        Reporter.NO_OP);

        Map<String, double[]> valuesByContingencyId = new HashMap<>(contingencies.size());
        Map<String, double[]> referencesByContingencyId = new HashMap<>(contingencies.size());
        for (int contingencyIndex = 0; contingencyIndex < contingencies.size(); contingencyIndex++) {
            Contingency contingency = contingencies.get(contingencyIndex);
            valuesByContingencyId.put(contingency.getId(), valuesByContingencyIndex[contingencyIndex]);
            referencesByContingencyId.put(contingency.getId(), referencesByContingencyIndex[contingencyIndex]);
        }

        return new SensitivityAnalysisResultContext(branchFlowFactorsMatrix,
                busVoltageFactorsMatrix,
                preContingencyFactorMatrix,
                postContingencyFactorMatrix,
                baseCaseValues,
                valuesByContingencyId,
                baseCaseReferences,
                referencesByContingencyId);
    }

}
