/**
 * Copyright (c) 2021, RTE (http://www.rte-france.com)
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.powsybl.python;

import javax.annotation.Nullable;
import java.util.Objects;

/**
 * @author Etienne Lesot <etienne.lesot at rte-france.com>
 */
public class NodeContext {
    private final int node;
    private final String connectableId;

    public NodeContext(int node, @Nullable String connectableId) {
        this.node = Objects.requireNonNull(node);
        this.connectableId = connectableId;
    }

    public int getNode() {
        return node;
    }

    public String getConnectableId() {
        return connectableId;
    }
}
