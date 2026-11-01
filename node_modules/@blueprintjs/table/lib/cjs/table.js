"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Table2 = exports.Table = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
/*
 * Copyright 2021 Palantir Technologies, Inc. All rights reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
const classnames_1 = tslib_1.__importDefault(require("classnames"));
const react_1 = require("react");
const react_innertext_1 = tslib_1.__importDefault(require("react-innertext"));
const core_1 = require("@blueprintjs/core");
const column_1 = require("./column");
const cellTypes_1 = require("./common/cellTypes");
const Classes = tslib_1.__importStar(require("./common/classes"));
const Errors = tslib_1.__importStar(require("./common/errors"));
const grid_1 = require("./common/grid");
const FocusedCellUtils = tslib_1.__importStar(require("./common/internal/focusedCellUtils"));
const ScrollUtils = tslib_1.__importStar(require("./common/internal/scrollUtils"));
const rect_1 = require("./common/rect");
const renderMode_1 = require("./common/renderMode");
const scrollDirection_1 = require("./common/scrollDirection");
const utils_1 = require("./common/utils");
const columnHeader_1 = require("./headers/columnHeader");
const columnHeaderCell_1 = require("./headers/columnHeaderCell");
const rowHeader_1 = require("./headers/rowHeader");
const resizeSensor_1 = require("./interactions/resizeSensor");
const guides_1 = require("./layers/guides");
const regions_1 = require("./layers/regions");
const locator_1 = require("./locator");
const tableQuadrant_1 = require("./quadrants/tableQuadrant");
const tableQuadrantStack_1 = require("./quadrants/tableQuadrantStack");
const regions_2 = require("./regions");
const resizeRows_1 = require("./resizeRows");
const tableBody_1 = require("./tableBody");
const tableHotkeys_1 = require("./tableHotkeys");
const tableUtils_1 = require("./tableUtils");
/**
 * Table component.
 *
 * @see https://blueprintjs.com/docs/#table/table
 */
class Table extends core_1.AbstractComponent {
    static displayName = `${core_1.DISPLAYNAME_PREFIX}.Table`;
    static defaultProps = {
        defaultColumnWidth: 150,
        defaultRowHeight: 20,
        enableColumnHeader: true,
        enableColumnInteractionBar: false,
        enableFocusedCell: false,
        enableGhostCells: false,
        enableMultipleSelection: true,
        enableRowHeader: true,
        forceRerenderOnSelectionChange: false,
        getCellClipboardData: (row, col, cellRenderer) => (0, react_innertext_1.default)(cellRenderer(row, col)),
        loadingOptions: [],
        maxColumnWidth: 9999,
        maxRowHeight: 9999,
        minColumnWidth: 50,
        minRowHeight: 20,
        numFrozenColumns: 0,
        numFrozenRows: 0,
        numRows: 0,
        renderMode: renderMode_1.RenderMode.BATCH_ON_UPDATE,
        rowHeaderCellRenderer: rowHeader_1.renderDefaultRowHeader,
        selectionModes: regions_2.SelectionModes.ALL,
    };
    static getDerivedStateFromProps(props, state) {
        const { children, defaultColumnWidth, defaultRowHeight, numRows, selectedRegions, selectionModes } = props;
        // assign values from state if uncontrolled
        let { columnWidths, rowHeights } = props;
        if (columnWidths == null) {
            columnWidths = state.columnWidths;
        }
        if (rowHeights == null) {
            rowHeights = state.rowHeights;
        }
        const newChildrenArray = react_1.Children.toArray(children);
        const didChildrenChange = !(0, tableUtils_1.compareChildren)(newChildrenArray, state.childrenArray);
        const numCols = newChildrenArray.length;
        let newColumnWidths = columnWidths;
        if (columnWidths !== state.columnWidths || didChildrenChange) {
            // Try to maintain widths of columns by looking up the width of the
            // column that had the same `ID` prop. If none is found, use the
            // previous width at the same index.
            const previousColumnWidths = newChildrenArray.map((child, index) => {
                const mappedIndex = child.props.id === undefined ? undefined : state.columnIdToIndex[child.props.id];
                return state.columnWidths[mappedIndex ?? index];
            });
            // Make sure the width/height arrays have the correct length, but keep
            // as many existing widths/heights as possible. Also, apply the
            // sparse width/heights from props.
            newColumnWidths = Array(numCols).fill(defaultColumnWidth);
            newColumnWidths = utils_1.Utils.assignSparseValues(newColumnWidths, previousColumnWidths);
            newColumnWidths = utils_1.Utils.assignSparseValues(newColumnWidths, columnWidths);
        }
        let newRowHeights = rowHeights;
        if (rowHeights !== state.rowHeights || numRows !== state.rowHeights.length) {
            newRowHeights = Array(numRows).fill(defaultRowHeight);
            newRowHeights = utils_1.Utils.assignSparseValues(newRowHeights, rowHeights);
        }
        const newSelectedRegions = selectedRegions ??
            state.selectedRegions.filter(region => {
                // if we're in uncontrolled mode, filter out all selected regions that don't
                // fit in the current new table dimensions
                const regionCardinality = regions_2.Regions.getRegionCardinality(region);
                return ((0, tableUtils_1.isSelectionModeEnabled)(props, regionCardinality, selectionModes) &&
                    regions_2.Regions.isRegionValidForTable(region, numRows, numCols));
            });
        const newFocusedRegion = FocusedCellUtils.getInitialFocusedRegion(FocusedCellUtils.getFocusModeFromProps(props), FocusedCellUtils.getFocusedRegionFromProps(props), state.focusedRegion, newSelectedRegions);
        const nextState = {
            childrenArray: newChildrenArray,
            columnIdToIndex: didChildrenChange ? Table.createColumnIdIndex(newChildrenArray) : state.columnIdToIndex,
            columnWidths: newColumnWidths,
            focusedRegion: newFocusedRegion,
            numFrozenColumnsClamped: (0, tableUtils_1.clampNumFrozenColumns)(props),
            numFrozenRowsClamped: (0, tableUtils_1.clampNumFrozenRows)(props),
            rowHeights: newRowHeights,
            selectedRegions: newSelectedRegions,
        };
        if (!core_1.Utils.deepCompareKeys(state, nextState, Table.SHALLOW_COMPARE_STATE_KEYS_DENYLIST)) {
            return nextState;
        }
        return null;
    }
    static SHALLOW_COMPARE_PROP_KEYS_DENYLIST = [
        "selectedRegions", // (intentionally omitted; can be deeply compared to save on re-renders in controlled mode)
    ];
    static SHALLOW_COMPARE_STATE_KEYS_DENYLIST = [
        "selectedRegions", // (intentionally omitted; can be deeply compared to save on re-renders in uncontrolled mode)
        "viewportRect",
    ];
    static createColumnIdIndex(children) {
        const columnIdToIndex = {};
        for (let i = 0; i < children.length; i++) {
            const key = children[i].props.id;
            if (key != null) {
                columnIdToIndex[String(key)] = i;
            }
        }
        return columnIdToIndex;
    }
    hotkeys = [];
    hotkeysImpl;
    grid = null;
    locator;
    resizeSensorDetach;
    refHandlers = {
        cellContainer: (ref) => (this.cellContainerElement = ref),
        columnHeader: (ref) => {
            if (ref != null) {
                this.columnHeaderHeight = Math.max(ref.clientHeight, grid_1.Grid.MIN_COLUMN_HEADER_HEIGHT);
            }
        },
        quadrantStack: (ref) => (this.quadrantStackInstance = ref),
        rootTable: (ref) => (this.rootTableElement = ref),
        rowHeader: (ref) => {
            if (ref != null) {
                this.rowHeaderWidth = ref.clientWidth;
            }
        },
        scrollContainer: (ref) => (this.scrollContainerElement = ref),
    };
    cellContainerElement;
    columnHeaderHeight = grid_1.Grid.MIN_COLUMN_HEADER_HEIGHT;
    quadrantStackInstance;
    rootTableElement;
    rowHeaderWidth = grid_1.Grid.MIN_ROW_HEADER_WIDTH;
    scrollContainerElement;
    didColumnHeaderMount = false;
    didRowHeaderMount = false;
    /*
     * This value is set to `true` when all cells finish mounting for the first
     * time. It serves as a signal that we can switch to batch rendering.
     */
    didCompletelyMount = false;
    constructor(props) {
        super(props);
        const { children, columnWidths, defaultRowHeight, defaultColumnWidth, enableRowHeader, numRows, rowHeights, selectedRegions = [], enableColumnHeader, } = props;
        const childrenArray = react_1.Children.toArray(children);
        const columnIdToIndex = Table.createColumnIdIndex(childrenArray);
        // Create height/width arrays using the lengths from props and
        // children, the default values from props, and finally any sparse
        // arrays passed into props.
        let newColumnWidths = childrenArray.map(() => defaultColumnWidth);
        if (columnWidths !== undefined) {
            newColumnWidths = utils_1.Utils.assignSparseValues(newColumnWidths, columnWidths);
        }
        let newRowHeights = utils_1.Utils.times(numRows, () => defaultRowHeight);
        if (rowHeights !== undefined) {
            newRowHeights = utils_1.Utils.assignSparseValues(newRowHeights, rowHeights);
        }
        const focusedRegion = FocusedCellUtils.getInitialFocusedRegion(FocusedCellUtils.getFocusModeFromProps(props), FocusedCellUtils.getFocusedRegionFromProps(props), undefined, selectedRegions);
        this.state = {
            childrenArray,
            columnIdToIndex,
            columnWidths: newColumnWidths,
            didHeadersMount: false,
            focusedRegion,
            horizontalGuides: [],
            isLayoutLocked: false,
            isReordering: false,
            numFrozenColumnsClamped: (0, tableUtils_1.clampNumFrozenColumns)(props),
            numFrozenRowsClamped: (0, tableUtils_1.clampNumFrozenRows)(props),
            rowHeights: newRowHeights,
            selectedRegions,
            verticalGuides: [],
        };
        this.hotkeysImpl = new tableHotkeys_1.TableHotkeys(props, this.state, {
            getEnabledSelectionHandler: this.getEnabledSelectionHandler,
            getHeaderDimensions: this.getHeaderDimensions,
            handleFocus: this.handleFocus,
            handleSelection: this.handleSelection,
            syncViewportPosition: this.syncViewportPosition,
        });
        this.hotkeys = (0, tableUtils_1.getHotkeysFromProps)(props, this.hotkeysImpl);
        if (enableRowHeader === false) {
            this.didRowHeaderMount = true;
        }
        if (enableColumnHeader === false) {
            this.didColumnHeaderMount = true;
        }
    }
    // Instance methods
    // ================
    /**
     * __Experimental!__ Resizes all rows in the table to the approximate
     * maximum height of wrapped cell content in each row. Works best when each
     * cell contains plain text of a consistent font style (though font style
     * may vary between cells). Since this function uses approximate
     * measurements, results may not be perfect.
     *
     * Approximation parameters can be configured for the entire table or on a
     * per-cell basis. Default values are fine-tuned to work well with default
     * Table font styles.
     */
    resizeRowsByApproximateHeight(getCellText, options) {
        const rowHeights = (0, resizeRows_1.resizeRowsByApproximateHeight)(this.props.numRows, this.state.columnWidths, getCellText, options);
        this.invalidateGrid();
        this.setState({ rowHeights });
    }
    /**
     * Resize all rows in the table to the height of the tallest visible cell in the specified columns.
     * If no indices are provided, default to using the tallest visible cell from all columns in view.
     */
    resizeRowsByTallestCell(columnIndices) {
        if (this.grid == null || this.state.viewportRect === undefined || this.locator === undefined) {
            console.warn(Errors.TABLE_UNMOUNTED_RESIZE_WARNING);
            return;
        }
        const rowHeights = (0, resizeRows_1.resizeRowsByTallestCell)(this.grid, this.state.viewportRect, this.locator, this.state.rowHeights.length, columnIndices);
        this.invalidateGrid();
        this.setState({ rowHeights });
    }
    /**
     * Scrolls the table to the target region in a fashion appropriate to the target region's
     * cardinality:
     *
     * - CELLS: Scroll the top-left cell in the target region to the top-left corner of the viewport.
     * - FULL_ROWS: Scroll the top-most row in the target region to the top of the viewport.
     * - FULL_COLUMNS: Scroll the left-most column in the target region to the left side of the viewport.
     * - FULL_TABLE: Scroll the top-left cell in the table to the top-left corner of the viewport.
     *
     * If there are active frozen rows and/or columns, the target region will be positioned in the
     * top-left corner of the non-frozen area (unless the target region itself is in the frozen
     * area).
     *
     * If the target region is close to the bottom-right corner of the table, this function will
     * simply scroll the target region as close to the top-left as possible until the bottom-right
     * corner is reached.
     */
    scrollToRegion(region) {
        const { numFrozenColumnsClamped: numFrozenColumns, numFrozenRowsClamped: numFrozenRows, viewportRect, } = this.state;
        if (viewportRect === undefined || this.grid === null || this.quadrantStackInstance === undefined) {
            return;
        }
        const { left: currScrollLeft, top: currScrollTop } = viewportRect;
        const { scrollLeft, scrollTop } = ScrollUtils.getScrollPositionForRegion(region, currScrollLeft, currScrollTop, this.grid.getCumulativeWidthBefore, this.grid.getCumulativeHeightBefore, numFrozenRows, numFrozenColumns);
        const correctedScrollLeft = this.shouldDisableHorizontalScroll() ? 0 : scrollLeft;
        const correctedScrollTop = this.shouldDisableVerticalScroll() ? 0 : scrollTop;
        // defer to the quadrant stack to keep all quadrant positions in sync
        this.quadrantStackInstance.scrollToPosition(correctedScrollLeft, correctedScrollTop);
    }
    /**
     * Scrolls the table by a specified number of offset pixels in either the horizontal or vertical dimension.
     * Will set a scroll indicator gradient which can be cleared by calling scrollByOffset(null);
     *
     * @param relativeOffset - How much to scroll the table body in pixels relative to the current scroll offset
     */
    scrollByOffset(relativeOffset) {
        let scrollDirection;
        if (relativeOffset) {
            if (Math.abs(relativeOffset.left) > Math.abs(relativeOffset.top)) {
                if (relativeOffset.left < 0) {
                    scrollDirection = scrollDirection_1.ScrollDirection.LEFT;
                }
                else {
                    scrollDirection = scrollDirection_1.ScrollDirection.RIGHT;
                }
            }
            else {
                if (relativeOffset.top < 0) {
                    scrollDirection = scrollDirection_1.ScrollDirection.TOP;
                }
                else {
                    scrollDirection = scrollDirection_1.ScrollDirection.BOTTOM;
                }
            }
        }
        if (this.shouldRenderScrollDirection(scrollDirection) || scrollDirection == null) {
            this.setState({ scrollDirection });
        }
        const { viewportRect } = this.state;
        if (viewportRect === undefined || this.grid === null || this.quadrantStackInstance === undefined) {
            return;
        }
        if (relativeOffset !== null) {
            const { left: currScrollLeft, top: currScrollTop } = viewportRect;
            const correctedScrollLeft = this.shouldDisableHorizontalScroll() ? 0 : currScrollLeft + relativeOffset.left;
            const correctedScrollTop = this.shouldDisableVerticalScroll() ? 0 : currScrollTop + relativeOffset.top;
            if (!this.shouldRenderScrollDirection(this.state.scrollDirection)) {
                this.setState({ scrollDirection: null });
            }
            // defer to the quadrant stack to keep all quadrant positions in sync
            this.quadrantStackInstance.scrollToPosition(correctedScrollLeft, correctedScrollTop);
        }
    }
    // React lifecycle
    // ===============
    shouldComponentUpdate(nextProps, nextState) {
        const propKeysDenylist = { exclude: Table.SHALLOW_COMPARE_PROP_KEYS_DENYLIST };
        const stateKeysDenylist = { exclude: Table.SHALLOW_COMPARE_STATE_KEYS_DENYLIST };
        return (!core_1.Utils.shallowCompareKeys(this.props, nextProps, propKeysDenylist) ||
            !core_1.Utils.shallowCompareKeys(this.state, nextState, stateKeysDenylist) ||
            !core_1.Utils.deepCompareKeys(this.props, nextProps, Table.SHALLOW_COMPARE_PROP_KEYS_DENYLIST) ||
            !core_1.Utils.deepCompareKeys(this.state, nextState, Table.SHALLOW_COMPARE_STATE_KEYS_DENYLIST));
    }
    render() {
        return (0, jsx_runtime_1.jsx)(core_1.HotkeysTarget, { hotkeys: this.hotkeys, children: this.renderTableContents });
    }
    renderTableContents = ({ handleKeyDown, handleKeyUp }) => {
        const { children, className, enableRowHeader, loadingOptions, numRows, enableColumnInteractionBar, enableColumnHeader, } = this.props;
        const { horizontalGuides, numFrozenColumnsClamped, numFrozenRowsClamped, verticalGuides } = this.state;
        if (!this.gridDimensionsMatchProps()) {
            // Ensure we're rendering the correct number of rows & columns
            this.invalidateGrid();
        }
        const grid = this.validateGrid();
        const classes = (0, classnames_1.default)(Classes.TABLE_CONTAINER, {
            [Classes.TABLE_REORDERING]: this.state.isReordering,
            [Classes.TABLE_NO_VERTICAL_SCROLL]: this.shouldDisableVerticalScroll(),
            [Classes.TABLE_NO_HORIZONTAL_SCROLL]: this.shouldDisableHorizontalScroll(),
            [Classes.TABLE_SELECTION_ENABLED]: (0, tableUtils_1.isSelectionModeEnabled)(this.props, regions_2.RegionCardinality.CELLS),
            [Classes.TABLE_NO_ROWS]: numRows === 0,
        }, className);
        return (
        // eslint-disable-next-line jsx-a11y/no-static-element-interactions
        (0, jsx_runtime_1.jsxs)("div", { className: classes, ref: this.refHandlers.rootTable, onScroll: this.handleRootScroll, onKeyDown: handleKeyDown, onKeyUp: handleKeyUp, 
            // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
            tabIndex: 0, children: [(0, jsx_runtime_1.jsx)(tableQuadrantStack_1.TableQuadrantStack, { bodyRef: this.refHandlers.cellContainer, bodyRenderer: this.renderBody, columnHeaderRenderer: this.renderColumnHeader, columnHeaderRef: this.refHandlers.columnHeader, didHeadersMount: this.state.didHeadersMount, enableColumnInteractionBar: enableColumnInteractionBar, enableRowHeader: enableRowHeader, grid: grid, handleColumnResizeGuide: this.handleColumnResizeGuide, handleColumnsReordering: this.handleColumnsReordering, handleRowResizeGuide: this.handleRowResizeGuide, handleRowsReordering: this.handleRowsReordering, isHorizontalScrollDisabled: this.shouldDisableHorizontalScroll(), isVerticalScrollDisabled: this.shouldDisableVerticalScroll(), loadingOptions: loadingOptions, numColumns: react_1.Children.count(children), numFrozenColumns: numFrozenColumnsClamped, numFrozenRows: numFrozenRowsClamped, numRows: numRows, onScroll: this.handleBodyScroll, ref: this.refHandlers.quadrantStack, menuRenderer: this.renderMenu, rowHeaderRenderer: this.renderRowHeader, rowHeaderRef: this.refHandlers.rowHeader, scrollContainerRef: this.refHandlers.scrollContainer, enableColumnHeader: enableColumnHeader, renderScrollIndicatorOverlay: this.renderScrollIndicatorOverlay }), (0, jsx_runtime_1.jsx)("div", { className: (0, classnames_1.default)(Classes.TABLE_OVERLAY_LAYER, Classes.TABLE_OVERLAY_REORDERING_CURSOR) }), (0, jsx_runtime_1.jsx)(guides_1.GuideLayer, { className: Classes.TABLE_RESIZE_GUIDES, verticalGuides: verticalGuides, horizontalGuides: horizontalGuides })] }));
    };
    /**
     * When the component mounts, the HTML Element refs will be available, so
     * we constructor the Locator, which queries the elements' bounding
     * ClientRects.
     */
    componentDidMount() {
        this.validateGrid();
        if (this.rootTableElement != null && this.scrollContainerElement != null && this.cellContainerElement != null) {
            this.locator = new locator_1.LocatorImpl(this.rootTableElement, this.scrollContainerElement, this.cellContainerElement);
            this.updateLocator();
            this.updateViewportRect(this.locator.getViewportRect());
            this.resizeSensorDetach = resizeSensor_1.ResizeSensor.attach(this.rootTableElement, () => {
                if (!this.state.isLayoutLocked) {
                    this.updateViewportRect(this.locator?.getViewportRect());
                }
            });
            this.forceUpdate();
        }
    }
    componentWillUnmount() {
        if (this.resizeSensorDetach != null) {
            this.resizeSensorDetach();
            delete this.resizeSensorDetach;
        }
        this.didCompletelyMount = false;
    }
    componentDidUpdate(prevProps, prevState) {
        super.componentDidUpdate(prevProps, prevState);
        this.hotkeysImpl.setState(this.state);
        this.hotkeysImpl.setProps(this.props);
        const didChildrenChange = !(0, tableUtils_1.compareChildren)(react_1.Children.toArray(this.props.children), this.state.childrenArray);
        if (this.props.cellRendererDependencies !== undefined && prevProps.cellRendererDependencies === undefined) {
            console.error(Errors.TABLE_INVALID_CELL_RENDERER_DEPS);
        }
        const didCellRendererDependenciesChange = this.props.cellRendererDependencies !== undefined &&
            this.props.cellRendererDependencies.some((dep, index) => dep !== (prevProps.cellRendererDependencies ?? [])[index]);
        const didColumnWidthsChange = !utils_1.Utils.compareSparseArrays(this.props.columnWidths ?? this.state.columnWidths, prevState.columnWidths);
        const didRowHeightsChange = !utils_1.Utils.compareSparseArrays(this.props.rowHeights ?? this.state.rowHeights, prevState.rowHeights);
        const shouldInvalidateGrid = didChildrenChange ||
            didCellRendererDependenciesChange ||
            didColumnWidthsChange ||
            didRowHeightsChange ||
            this.props.numRows !== prevProps.numRows ||
            (this.props.forceRerenderOnSelectionChange && this.props.selectedRegions !== prevProps.selectedRegions);
        if (shouldInvalidateGrid) {
            this.invalidateGrid();
        }
        if (this.locator != null) {
            this.validateGrid();
            this.updateLocator();
        }
        const newFocusMode = FocusedCellUtils.getFocusModeFromProps(this.props);
        const didFocusModeChange = newFocusMode !== FocusedCellUtils.getFocusModeFromProps(prevProps);
        const shouldInvalidateHotkeys = didFocusModeChange ||
            this.props.getCellClipboardData !== prevProps.getCellClipboardData ||
            this.props.enableMultipleSelection !== prevProps.enableMultipleSelection ||
            this.props.selectionModes !== prevProps.selectionModes;
        if (shouldInvalidateHotkeys) {
            this.hotkeys = (0, tableUtils_1.getHotkeysFromProps)(this.props, this.hotkeysImpl);
        }
        if (didCellRendererDependenciesChange) {
            // force an update with the new grid
            this.forceUpdate();
        }
    }
    validateProps(props) {
        const { children, columnWidths, numFrozenColumns, numFrozenRows, numRows, rowHeights } = props;
        const numColumns = react_1.Children.count(children);
        // do cheap error-checking first.
        if (numRows != null && numRows < 0) {
            throw new Error(Errors.TABLE_NUM_ROWS_NEGATIVE);
        }
        if (numFrozenRows != null && numFrozenRows < 0) {
            throw new Error(Errors.TABLE_NUM_FROZEN_ROWS_NEGATIVE);
        }
        if (numFrozenColumns != null && numFrozenColumns < 0) {
            throw new Error(Errors.TABLE_NUM_FROZEN_COLUMNS_NEGATIVE);
        }
        if (numRows != null && rowHeights != null && rowHeights.length !== numRows) {
            throw new Error(Errors.TABLE_NUM_ROWS_ROW_HEIGHTS_MISMATCH);
        }
        if (numColumns != null && columnWidths != null && columnWidths.length !== numColumns) {
            throw new Error(Errors.TABLE_NUM_COLUMNS_COLUMN_WIDTHS_MISMATCH);
        }
        react_1.Children.forEach(children, child => {
            if (!core_1.Utils.isElementOfType(child, column_1.Column)) {
                throw new Error(Errors.TABLE_NON_COLUMN_CHILDREN_WARNING);
            }
        });
        // these are recoverable scenarios, so just print a warning.
        if (numFrozenRows != null && numRows != null && numFrozenRows > numRows) {
            console.warn(Errors.TABLE_NUM_FROZEN_ROWS_BOUND_WARNING);
        }
        if (numFrozenColumns != null && numFrozenColumns > numColumns) {
            console.warn(Errors.TABLE_NUM_FROZEN_COLUMNS_BOUND_WARNING);
        }
    }
    gridDimensionsMatchProps() {
        const { children, numRows } = this.props;
        return this.grid != null && this.grid.numCols === react_1.Children.count(children) && this.grid.numRows === numRows;
    }
    // Quadrant refs
    // =============
    shouldDisableVerticalScroll() {
        const { enableGhostCells } = this.props;
        const { viewportRect } = this.state;
        if (this.grid === null || viewportRect === undefined) {
            return false;
        }
        const rowIndices = this.grid.getRowIndicesInRect({
            columnHeaderHeight: this.getColumnHeaderHeight(),
            includeGhostCells: enableGhostCells,
            rect: viewportRect,
        });
        const isViewportUnscrolledVertically = viewportRect != null && viewportRect.top === 0;
        const areRowHeadersLoading = (0, tableUtils_1.hasLoadingOption)(this.props.loadingOptions, regions_2.TableLoadingOption.ROW_HEADERS);
        const areGhostRowsVisible = enableGhostCells && this.grid.isGhostIndex(rowIndices.rowIndexEnd, 0);
        return areGhostRowsVisible && (isViewportUnscrolledVertically || areRowHeadersLoading);
    }
    shouldDisableHorizontalScroll() {
        const { enableGhostCells } = this.props;
        const { viewportRect } = this.state;
        if (this.grid === null || viewportRect === undefined) {
            return false;
        }
        const columnIndices = this.grid.getColumnIndicesInRect(viewportRect, enableGhostCells);
        const isViewportUnscrolledHorizontally = viewportRect != null && viewportRect.left === 0;
        const areColumnHeadersLoading = (0, tableUtils_1.hasLoadingOption)(this.props.loadingOptions, regions_2.TableLoadingOption.COLUMN_HEADERS);
        const areGhostColumnsVisible = enableGhostCells && this.grid.isGhostColumn(columnIndices.columnIndexEnd);
        return areGhostColumnsVisible && (isViewportUnscrolledHorizontally || areColumnHeadersLoading);
    }
    shouldRenderScrollDirection(scrollDirection) {
        if (!this.scrollContainerElement || !this.state.viewportRect) {
            return false;
        }
        const scrollWrapper = this.scrollContainerElement;
        const { left: currScrollLeft, top: currScrollTop } = this.state.viewportRect;
        switch (scrollDirection) {
            case "left":
                return currScrollLeft > 0;
            case "right":
                return scrollWrapper.scrollWidth - scrollWrapper.offsetWidth !== currScrollLeft;
            case "top":
                return currScrollTop > 0;
            case "bottom":
                return scrollWrapper.scrollHeight - scrollWrapper.offsetHeight !== currScrollTop;
            default:
                return false;
        }
    }
    renderMenu = (refHandler) => {
        const classes = (0, classnames_1.default)(Classes.TABLE_MENU, {
            [Classes.TABLE_SELECTION_ENABLED]: (0, tableUtils_1.isSelectionModeEnabled)(this.props, regions_2.RegionCardinality.FULL_TABLE),
        });
        return (
        // eslint-disable-next-line jsx-a11y/no-static-element-interactions
        (0, jsx_runtime_1.jsx)("div", { className: classes, ref: refHandler, onMouseDown: this.handleMenuMouseDown, children: this.maybeRenderRegions(this.styleMenuRegion) }));
    };
    handleMenuMouseDown = (e) => {
        // the shift+click interaction expands the region from the focused cell.
        // thus, if shift is pressed we shouldn't move the focused cell.
        this.selectAll(!e.shiftKey);
    };
    selectAll = (shouldUpdateFocusedCell) => {
        const selectionHandler = this.getEnabledSelectionHandler(regions_2.RegionCardinality.FULL_TABLE);
        // clicking on upper left hand corner sets selection to "all"
        // regardless of current selection state (clicking twice does not deselect table)
        selectionHandler([regions_2.Regions.table()]);
        if (shouldUpdateFocusedCell) {
            const focusMode = FocusedCellUtils.getFocusModeFromProps(this.props);
            const newFocusedCellCoordinates = regions_2.Regions.getFocusCellCoordinatesFromRegion(regions_2.Regions.table());
            const newFocusedRegion = FocusedCellUtils.toFocusedRegion(focusMode, newFocusedCellCoordinates);
            if (newFocusedRegion != null) {
                this.handleFocus(newFocusedRegion);
            }
        }
    };
    getColumnProps(columnIndex) {
        const column = this.state.childrenArray[columnIndex];
        return column === undefined ? undefined : column.props;
    }
    columnHeaderCellRenderer = (columnIndex) => {
        const columnProps = this.getColumnProps(columnIndex);
        if (columnProps === undefined) {
            return null;
        }
        const { id, cellRenderer, columnHeaderCellRenderer, ...spreadableProps } = columnProps;
        const columnLoading = (0, tableUtils_1.hasLoadingOption)(columnProps.loadingOptions, regions_2.ColumnLoadingOption.HEADER) ||
            (0, tableUtils_1.hasLoadingOption)(this.props.loadingOptions, regions_2.TableLoadingOption.COLUMN_HEADERS);
        if (columnHeaderCellRenderer != null) {
            const columnHeaderCell = columnHeaderCellRenderer(columnIndex);
            if (columnHeaderCell != null) {
                return (0, react_1.cloneElement)(columnHeaderCell, {
                    enableColumnInteractionBar: this.props.enableColumnInteractionBar,
                    loading: columnHeaderCell.props.loading ?? columnLoading,
                });
            }
        }
        const baseProps = {
            enableColumnInteractionBar: this.props.enableColumnInteractionBar,
            index: columnIndex,
            loading: columnLoading,
            ...spreadableProps,
        };
        if (columnProps.name != null) {
            return (0, jsx_runtime_1.jsx)(columnHeaderCell_1.ColumnHeaderCell, { ...baseProps });
        }
        else {
            return (0, jsx_runtime_1.jsx)(columnHeaderCell_1.ColumnHeaderCell, { ...baseProps, name: utils_1.Utils.toBase26Alpha(columnIndex) });
        }
    };
    renderColumnHeader = (refHandler, resizeHandler, reorderingHandler, showFrozenColumnsOnly = false) => {
        const { focusedRegion, selectedRegions, viewportRect } = this.state;
        const { defaultColumnWidth, enableMultipleSelection, enableGhostCells, enableColumnReordering, enableColumnResizing, loadingOptions, maxColumnWidth, minColumnWidth, selectedRegionTransform, } = this.props;
        const classes = (0, classnames_1.default)(Classes.TABLE_COLUMN_HEADERS, {
            [Classes.TABLE_SELECTION_ENABLED]: (0, tableUtils_1.isSelectionModeEnabled)(this.props, regions_2.RegionCardinality.FULL_COLUMNS),
        });
        if (this.grid === null || this.locator === undefined || viewportRect === undefined) {
            // if we haven't mounted yet (which we need in order for grid/viewport calculations),
            // we still want to hand a DOM ref over to TableQuadrantStack for later
            return (0, jsx_runtime_1.jsx)("div", { className: classes, ref: refHandler });
        }
        // if we have horizontal overflow or exact fit, no need to render ghost columns
        // (this avoids problems like https://github.com/palantir/blueprint/issues/5027)
        const hasHorizontalOverflowOrExactFit = this.locator.hasHorizontalOverflowOrExactFit(this.getRowHeaderWidth(), viewportRect);
        const columnIndices = this.grid.getColumnIndicesInRect(viewportRect, hasHorizontalOverflowOrExactFit ? false : enableGhostCells);
        const columnIndexStart = showFrozenColumnsOnly ? 0 : columnIndices.columnIndexStart;
        const columnIndexEnd = showFrozenColumnsOnly ? this.getMaxFrozenColumnIndex() : columnIndices.columnIndexEnd;
        return ((0, jsx_runtime_1.jsxs)("div", { className: classes, ref: refHandler, children: [(0, jsx_runtime_1.jsx)(columnHeader_1.ColumnHeader, { defaultColumnWidth: defaultColumnWidth, enableMultipleSelection: enableMultipleSelection, cellRenderer: this.columnHeaderCellRenderer, focusedRegion: focusedRegion, focusMode: FocusedCellUtils.getFocusModeFromProps(this.props), grid: this.grid, isReorderable: enableColumnReordering, isResizable: enableColumnResizing, loading: (0, tableUtils_1.hasLoadingOption)(loadingOptions, regions_2.TableLoadingOption.COLUMN_HEADERS), locator: this.locator, maxColumnWidth: maxColumnWidth, minColumnWidth: minColumnWidth, onColumnWidthChanged: this.handleColumnWidthChanged, onFocusedRegion: this.handleFocus, onMount: this.handleHeaderMounted, onLayoutLock: this.handleLayoutLock, onReordered: this.handleColumnsReordered, onReordering: reorderingHandler, onResizeGuide: resizeHandler, onSelection: this.getEnabledSelectionHandler(regions_2.RegionCardinality.FULL_COLUMNS), selectedRegions: selectedRegions, selectedRegionTransform: selectedRegionTransform, columnIndexStart: columnIndexStart, columnIndexEnd: columnIndexEnd, children: this.props.children }), this.maybeRenderRegions(this.styleColumnHeaderRegion)] }));
    };
    renderRowHeader = (refHandler, resizeHandler, reorderingHandler, showFrozenRowsOnly = false) => {
        const { focusedRegion, selectedRegions, viewportRect } = this.state;
        const { defaultRowHeight, enableMultipleSelection, enableGhostCells, enableRowReordering, enableRowResizing, loadingOptions, maxRowHeight, minRowHeight, rowHeaderCellRenderer, selectedRegionTransform, } = this.props;
        const classes = (0, classnames_1.default)(Classes.TABLE_ROW_HEADERS, {
            [Classes.TABLE_SELECTION_ENABLED]: (0, tableUtils_1.isSelectionModeEnabled)(this.props, regions_2.RegionCardinality.FULL_ROWS),
        });
        if (this.grid === null || this.locator === undefined || viewportRect === undefined) {
            // if we haven't mounted yet (which we need in order for grid/viewport calculations),
            // we still want to hand a DOM ref over to TableQuadrantStack for later
            return (0, jsx_runtime_1.jsx)("div", { className: classes, ref: refHandler });
        }
        // if we have vertical overflow or exact fit, no need to render ghost rows
        // (this avoids problems like https://github.com/palantir/blueprint/issues/5027)
        const hasVerticalOverflowOrExactFit = this.locator.hasVerticalOverflowOrExactFit(this.getColumnHeaderHeight(), viewportRect);
        const rowIndices = this.grid.getRowIndicesInRect({
            includeGhostCells: hasVerticalOverflowOrExactFit ? false : enableGhostCells,
            rect: viewportRect,
        });
        const rowIndexStart = showFrozenRowsOnly ? 0 : rowIndices.rowIndexStart;
        const rowIndexEnd = showFrozenRowsOnly ? this.getMaxFrozenRowIndex() : rowIndices.rowIndexEnd;
        return ((0, jsx_runtime_1.jsxs)("div", { className: classes, ref: refHandler, children: [(0, jsx_runtime_1.jsx)(rowHeader_1.RowHeader, { defaultRowHeight: defaultRowHeight, enableMultipleSelection: enableMultipleSelection, focusedRegion: focusedRegion, focusMode: FocusedCellUtils.getFocusModeFromProps(this.props), grid: this.grid, locator: this.locator, isReorderable: enableRowReordering, isResizable: enableRowResizing, loading: (0, tableUtils_1.hasLoadingOption)(loadingOptions, regions_2.TableLoadingOption.ROW_HEADERS), maxRowHeight: maxRowHeight, minRowHeight: minRowHeight, onFocusedRegion: this.handleFocus, onLayoutLock: this.handleLayoutLock, onMount: this.handleHeaderMounted, onResizeGuide: resizeHandler, onReordered: this.handleRowsReordered, onReordering: reorderingHandler, onRowHeightChanged: this.handleRowHeightChanged, onSelection: this.getEnabledSelectionHandler(regions_2.RegionCardinality.FULL_ROWS), rowHeaderCellRenderer: rowHeaderCellRenderer, selectedRegions: selectedRegions, selectedRegionTransform: selectedRegionTransform, rowIndexStart: rowIndexStart, rowIndexEnd: rowIndexEnd }), this.maybeRenderRegions(this.styleRowHeaderRegion)] }));
    };
    bodyCellRenderer = (rowIndex, columnIndex) => {
        const columnProps = this.getColumnProps(columnIndex);
        if (columnProps === undefined) {
            return undefined;
        }
        const { id, cellRenderer, columnHeaderCellRenderer, name, nameRenderer, ...restColumnProps } = columnProps;
        // HACKHACK: cellRenderer prop has a default value, so we can assert non-null
        const cell = cellRenderer(rowIndex, columnIndex);
        if (cell === undefined) {
            return undefined;
        }
        const inheritedIsLoading = (0, tableUtils_1.hasLoadingOption)(columnProps.loadingOptions, regions_2.ColumnLoadingOption.CELLS) ||
            (0, tableUtils_1.hasLoadingOption)(this.props.loadingOptions, regions_2.TableLoadingOption.CELLS);
        return (0, react_1.cloneElement)(cell, {
            ...restColumnProps,
            loading: cell.props.loading ?? inheritedIsLoading,
        });
    };
    renderBody = (quadrantType, showFrozenRowsOnly = false, showFrozenColumnsOnly = false) => {
        const { focusedRegion, numFrozenColumnsClamped: numFrozenColumns, numFrozenRowsClamped: numFrozenRows, selectedRegions, viewportRect, } = this.state;
        const { enableMultipleSelection, enableColumnHeader, enableGhostCells, loadingOptions, bodyContextMenuRenderer, selectedRegionTransform, } = this.props;
        if (this.grid === null || this.locator === undefined || viewportRect === undefined) {
            return undefined;
        }
        // if we have vertical/horizontal overflow or exact fit, no need to render ghost rows/columns (respectively)
        // (this avoids problems like https://github.com/palantir/blueprint/issues/5027)
        const hasVerticalOverflowOrExactFit = this.locator.hasVerticalOverflowOrExactFit(enableColumnHeader ? this.columnHeaderHeight : 0, viewportRect);
        const hasHorizontalOverflowOrExactFit = this.locator.hasHorizontalOverflowOrExactFit(this.getRowHeaderWidth(), viewportRect);
        const rowIndices = this.grid.getRowIndicesInRect({
            includeGhostCells: hasVerticalOverflowOrExactFit ? false : enableGhostCells,
            rect: viewportRect,
        });
        const columnIndices = this.grid.getColumnIndicesInRect(viewportRect, hasHorizontalOverflowOrExactFit ? false : enableGhostCells);
        // start beyond the frozen area if rendering unrelated quadrants, so we
        // don't render duplicate cells underneath the frozen ones.
        const columnIndexStart = showFrozenColumnsOnly ? 0 : columnIndices.columnIndexStart + numFrozenColumns;
        const rowIndexStart = showFrozenRowsOnly ? 0 : rowIndices.rowIndexStart + numFrozenRows;
        // if rendering frozen rows/columns, subtract one to convert to
        // 0-indexing. if the 1-indexed value is 0, this sets the end index
        // to -1, which avoids rendering absent frozen rows/columns at all.
        const columnIndexEnd = showFrozenColumnsOnly ? numFrozenColumns - 1 : columnIndices.columnIndexEnd;
        const rowIndexEnd = showFrozenRowsOnly ? numFrozenRows - 1 : rowIndices.rowIndexEnd;
        // the main quadrant contains all cells in the table, so listen only to that quadrant
        const onCompleteRender = quadrantType === tableQuadrant_1.QuadrantType.MAIN ? this.handleCompleteRender : undefined;
        return ((0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)(tableBody_1.TableBody, { enableMultipleSelection: enableMultipleSelection, cellRenderer: this.bodyCellRenderer, focusedRegion: focusedRegion, focusMode: FocusedCellUtils.getFocusModeFromProps(this.props), grid: this.grid, loading: (0, tableUtils_1.hasLoadingOption)(loadingOptions, regions_2.TableLoadingOption.CELLS), locator: this.locator, onCompleteRender: onCompleteRender, onFocusedRegion: this.handleFocus, onSelection: this.getEnabledSelectionHandler(regions_2.RegionCardinality.CELLS), bodyContextMenuRenderer: bodyContextMenuRenderer, renderMode: this.getNormalizedRenderMode(), selectedRegions: selectedRegions, selectedRegionTransform: selectedRegionTransform, viewportRect: viewportRect, columnIndexStart: columnIndexStart, columnIndexEnd: columnIndexEnd, rowIndexStart: rowIndexStart, rowIndexEnd: rowIndexEnd, numFrozenColumns: showFrozenColumnsOnly ? numFrozenColumns : undefined, numFrozenRows: showFrozenRowsOnly ? numFrozenRows : undefined }), this.maybeRenderRegions(this.styleBodyRegion, quadrantType)] }));
    };
    isGuideLayerShowing() {
        return this.state.verticalGuides.length > 0 || this.state.horizontalGuides.length > 0;
    }
    getEnabledSelectionHandler = (selectionMode) => {
        if (!(0, tableUtils_1.isSelectionModeEnabled)(this.props, selectionMode)) {
            // If the selection mode isn't enabled, return a callback that
            // will clear the selection. For example, if row selection is
            // disabled, clicking on the row header will clear the table's
            // selection. If all selection modes are enabled, clicking on the
            // same region twice will clear the selection.
            return this.clearSelection;
        }
        else {
            return this.handleSelection;
        }
    };
    invalidateGrid() {
        this.grid = null;
    }
    /**
     * This method's arguments allow us to support the following use case:
     * In some cases, we want to update the grid _before_ this.setState() is called with updated
     * `columnWidths` or `rowHeights` so that when that setState update _does_ flush through the React render
     * tree, our TableQuadrantStack has the correct updated grid measurements.
     */
    validateGrid({ columnWidths, rowHeights } = {}) {
        if (this.grid == null || columnWidths !== undefined || rowHeights !== undefined) {
            const { defaultRowHeight, defaultColumnWidth, numFrozenColumns } = this.props;
            // gridBleed should always be >= numFrozenColumns since columnIndexStart adds numFrozenColumns
            const gridBleed = Math.max(grid_1.Grid.DEFAULT_BLEED, numFrozenColumns);
            this.grid = new grid_1.Grid(rowHeights ?? this.state.rowHeights, columnWidths ?? this.state.columnWidths, gridBleed, defaultRowHeight, defaultColumnWidth);
            this.invokeOnVisibleCellsChangeCallback(this.state.viewportRect);
            this.hotkeysImpl.setGrid(this.grid);
        }
        return this.grid;
    }
    /**
     * Renders a scroll indicator overlay on top of the table body inside the quadrant stack.
     * This component is offset by the headers and scrollbar, and it provides the overlay which
     * we use to render automatic scrolling indicator linear gradients.
     *
     * @param scrollBarWidth the calculated scroll bar width to be passed in by the quadrant stack
     * @param columnHeaderHeight the calculated column header height to be passed in by the quadrant stack
     * @returns A jsx element which will render a linear gradient with smooth transitions based on
     *          state of the scroll (will not render if we are already at the top/left/right/bottom)
     *           and the state of "scroll direction"
     */
    renderScrollIndicatorOverlay = (scrollBarWidth, columnHeaderHeight) => {
        const { scrollDirection } = this.state;
        const getStyle = (direction, compare) => {
            return {
                marginRight: scrollBarWidth,
                marginTop: columnHeaderHeight,
                opacity: direction === compare ? 1 : 0,
            };
        };
        const baseClass = Classes.TABLE_BODY_SCROLLING_INDICATOR_OVERLAY;
        return ((0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsx)("div", { className: (0, classnames_1.default)(baseClass, Classes.TABLE_BODY_IS_SCROLLING_TOP), style: getStyle(scrollDirection, scrollDirection_1.ScrollDirection.TOP) }), (0, jsx_runtime_1.jsx)("div", { className: (0, classnames_1.default)(baseClass, Classes.TABLE_BODY_IS_SCROLLING_BOTTOM), style: getStyle(scrollDirection, scrollDirection_1.ScrollDirection.BOTTOM) }), (0, jsx_runtime_1.jsx)("div", { className: (0, classnames_1.default)(baseClass, Classes.TABLE_BODY_IS_SCROLLING_RIGHT), style: getStyle(scrollDirection, scrollDirection_1.ScrollDirection.RIGHT) }), (0, jsx_runtime_1.jsx)("div", { className: (0, classnames_1.default)(baseClass, Classes.TABLE_BODY_IS_SCROLLING_LEFT), style: getStyle(scrollDirection, scrollDirection_1.ScrollDirection.LEFT) })] }));
    };
    /**
     * Renders a `RegionLayer`, applying styles to the regions using the
     * supplied `RegionStyler`. `RegionLayer` is a pure component, so
     * the `RegionStyler` should be a new instance on every render if we
     * intend to redraw the region layer.
     */
    maybeRenderRegions(getRegionStyle, quadrantType) {
        if (this.isGuideLayerShowing() && !this.state.isReordering) {
            // we want to show guides *and* the selection styles when reordering rows or columns
            return undefined;
        }
        const regionGroups = regions_2.Regions.joinStyledRegionGroups(this.state.selectedRegions, this.props.styledRegionGroups ?? [], this.state.focusedRegion);
        return regionGroups.map((regionGroup, index) => {
            const regionStyles = regionGroup.regions.map(region => getRegionStyle(region, quadrantType));
            return ((0, jsx_runtime_1.jsx)(regions_1.RegionLayer, { className: (0, classnames_1.default)(regionGroup.className), regions: regionGroup.regions, regionStyles: regionStyles }, index));
        });
    }
    handleHeaderMounted = (whichHeader) => {
        const { didHeadersMount } = this.state;
        if (didHeadersMount) {
            return;
        }
        if (whichHeader === "column") {
            this.didColumnHeaderMount = true;
        }
        else {
            this.didRowHeaderMount = true;
        }
        if (this.didColumnHeaderMount && this.didRowHeaderMount) {
            this.setState({ didHeadersMount: true });
        }
    };
    handleCompleteRender = () => {
        // The first onCompleteRender is triggered before the viewportRect is
        // defined and the second after the viewportRect has been set. The cells
        // will only actually render once the viewportRect is defined though, so
        // we defer invoking onCompleteRender until that check passes.
        // Additional note: we run into an unfortunate race condition between the order of execution
        // of this callback and this.handleHeaderMounted(...). The setState() call in the latter
        // does not update this.state quickly enough for us to query for the new state here, so instead
        // we read the private member variables which are the dependent parts of that "didHeadersMount"
        // state.
        const didHeadersMount = this.didColumnHeaderMount && this.didRowHeaderMount;
        if (this.state.viewportRect != null && didHeadersMount) {
            this.props.onCompleteRender?.();
            this.didCompletelyMount = true;
        }
    };
    styleBodyRegion = (region, quadrantType) => {
        const { numFrozenColumns } = this.props;
        if (this.grid == null) {
            return {};
        }
        const cardinality = regions_2.Regions.getRegionCardinality(region);
        const style = this.grid.getRegionStyle(region);
        // ensure we're not showing borders at the boundary of the frozen-columns area
        const canHideRightBorder = (quadrantType === tableQuadrant_1.QuadrantType.TOP_LEFT || quadrantType === tableQuadrant_1.QuadrantType.LEFT) &&
            numFrozenColumns != null &&
            numFrozenColumns > 0;
        const fixedHeight = this.grid.getHeight();
        const fixedWidth = this.grid.getWidth();
        // include a correction in some cases to hide borders along quadrant boundaries
        const alignmentCorrection = 1;
        const alignmentCorrectionString = `-${alignmentCorrection}px`;
        switch (cardinality) {
            case regions_2.RegionCardinality.CELLS:
                return style;
            case regions_2.RegionCardinality.FULL_COLUMNS:
                style.top = alignmentCorrectionString;
                style.height = fixedHeight + alignmentCorrection;
                return style;
            case regions_2.RegionCardinality.FULL_ROWS:
                style.left = alignmentCorrectionString;
                style.width = fixedWidth + alignmentCorrection;
                if (canHideRightBorder) {
                    style.right = alignmentCorrectionString;
                }
                return style;
            case regions_2.RegionCardinality.FULL_TABLE:
                style.left = alignmentCorrectionString;
                style.top = alignmentCorrectionString;
                style.width = fixedWidth + alignmentCorrection;
                style.height = fixedHeight + alignmentCorrection;
                if (canHideRightBorder) {
                    style.right = alignmentCorrectionString;
                }
                return style;
            default:
                return { display: "none" };
        }
    };
    styleMenuRegion = (region) => {
        const { viewportRect } = this.state;
        if (this.grid == null || viewportRect == null) {
            return {};
        }
        const cardinality = regions_2.Regions.getRegionCardinality(region);
        const style = this.grid.getRegionStyle(region);
        switch (cardinality) {
            case regions_2.RegionCardinality.FULL_TABLE:
                style.right = "0px";
                style.bottom = "0px";
                style.top = "0px";
                style.left = "0px";
                style.borderBottom = "none";
                style.borderRight = "none";
                return style;
            default:
                return { display: "none" };
        }
    };
    styleColumnHeaderRegion = (region) => {
        const { viewportRect } = this.state;
        if (this.grid == null || viewportRect == null) {
            return {};
        }
        const cardinality = regions_2.Regions.getRegionCardinality(region);
        const style = this.grid.getRegionStyle(region);
        switch (cardinality) {
            case regions_2.RegionCardinality.FULL_TABLE:
                style.left = "-1px";
                style.borderLeft = "none";
                style.bottom = "-1px";
                return style;
            case regions_2.RegionCardinality.FULL_COLUMNS:
                style.bottom = "-1px";
                return style;
            default:
                return { display: "none" };
        }
    };
    styleRowHeaderRegion = (region) => {
        const { viewportRect } = this.state;
        if (this.grid == null || viewportRect == null) {
            return {};
        }
        const cardinality = regions_2.Regions.getRegionCardinality(region);
        const style = this.grid.getRegionStyle(region);
        switch (cardinality) {
            case regions_2.RegionCardinality.FULL_TABLE:
                style.top = "-1px";
                style.borderTop = "none";
                style.right = "-1px";
                return style;
            case regions_2.RegionCardinality.FULL_ROWS:
                style.right = "-1px";
                return style;
            default:
                return { display: "none" };
        }
    };
    handleColumnWidthChanged = (columnIndex, width) => {
        const selectedRegions = this.state.selectedRegions;
        const columnWidths = this.state.columnWidths.slice();
        if (regions_2.Regions.hasFullTable(selectedRegions)) {
            for (let col = 0; col < columnWidths.length; col++) {
                columnWidths[col] = width;
            }
        }
        if (regions_2.Regions.hasFullColumn(selectedRegions, columnIndex)) {
            regions_2.Regions.eachUniqueFullColumn(selectedRegions, (col) => {
                columnWidths[col] = width;
            });
        }
        else {
            columnWidths[columnIndex] = width;
        }
        this.validateGrid({ columnWidths });
        this.setState({ columnWidths });
        this.props.onColumnWidthChanged?.(columnIndex, width);
    };
    handleRowHeightChanged = (rowIndex, height) => {
        const selectedRegions = this.state.selectedRegions;
        const rowHeights = this.state.rowHeights.slice();
        if (regions_2.Regions.hasFullTable(selectedRegions)) {
            for (let row = 0; row < rowHeights.length; row++) {
                rowHeights[row] = height;
            }
        }
        if (regions_2.Regions.hasFullRow(selectedRegions, rowIndex)) {
            regions_2.Regions.eachUniqueFullRow(selectedRegions, (row) => {
                rowHeights[row] = height;
            });
        }
        else {
            rowHeights[rowIndex] = height;
        }
        this.validateGrid({ rowHeights });
        this.setState({ rowHeights });
        this.props.onRowHeightChanged?.(rowIndex, height);
    };
    handleRootScroll = (_event) => {
        // Bug #211 - Native browser text selection events can cause the root
        // element to scroll even though it has a overflow:hidden style. The
        // only viable solution to this is to unscroll the element after the
        // browser scrolls it.
        if (this.rootTableElement != null) {
            this.rootTableElement.scrollLeft = 0;
            this.rootTableElement.scrollTop = 0;
        }
    };
    handleBodyScroll = (event) => {
        // Prevent the event from propagating to avoid a resize event on the resize sensor.
        event.stopPropagation();
        if (this.locator != null && !this.state.isLayoutLocked) {
            const newViewportRect = this.locator.getViewportRect();
            this.updateViewportRect(newViewportRect);
        }
    };
    clearSelection = (_selectedRegions) => {
        this.handleSelection([]);
    };
    syncViewportPosition = ({ nextScrollLeft, nextScrollTop }) => {
        const { viewportRect } = this.state;
        if (this.scrollContainerElement == null || viewportRect === undefined) {
            return;
        }
        if (nextScrollLeft !== undefined || nextScrollTop !== undefined) {
            if (nextScrollTop !== undefined) {
                this.scrollContainerElement.scrollTop = nextScrollTop;
            }
            if (nextScrollLeft !== undefined) {
                this.scrollContainerElement.scrollLeft = nextScrollLeft;
            }
            const nextViewportRect = new rect_1.Rect(nextScrollLeft ?? viewportRect.left, nextScrollTop ?? viewportRect.top, viewportRect.width, viewportRect.height);
            this.updateViewportRect(nextViewportRect);
        }
    };
    handleFocus = (focusedRegion) => {
        if (FocusedCellUtils.getFocusModeFromProps(this.props) !== focusedRegion?.type) {
            // don't set focus state if given focus mode is not enabled
            return;
        }
        // only set focused region state if not specified in props
        if (FocusedCellUtils.getFocusedRegionFromProps(this.props) == null) {
            this.setState({ focusedRegion });
        }
        if (focusedRegion == null) {
            return;
        }
        if (focusedRegion.type === cellTypes_1.FocusMode.CELL) {
            const { type, ...focusedCell } = focusedRegion;
            // eslint-disable-next-line @typescript-eslint/no-deprecated
            this.props.onFocusedCell?.(focusedCell);
        }
        this.props.onFocusedRegion?.(focusedRegion);
    };
    handleSelection = (selectedRegions) => {
        // only set selectedRegions state if not specified in props
        if (this.props.selectedRegions == null) {
            this.setState({ selectedRegions });
        }
        const { onSelection } = this.props;
        if (onSelection != null) {
            onSelection(selectedRegions);
        }
    };
    handleColumnsReordering = (verticalGuides) => {
        this.setState({ isReordering: true, verticalGuides });
    };
    handleColumnsReordered = (oldIndex, newIndex, length) => {
        this.setState({ isReordering: false, verticalGuides: [] });
        this.props.onColumnsReordered?.(oldIndex, newIndex, length);
    };
    handleRowsReordering = (horizontalGuides) => {
        this.setState({ horizontalGuides, isReordering: true });
    };
    handleRowsReordered = (oldIndex, newIndex, length) => {
        this.setState({ horizontalGuides: [], isReordering: false });
        this.props.onRowsReordered?.(oldIndex, newIndex, length);
    };
    handleLayoutLock = (isLayoutLocked = false) => {
        this.setState({ isLayoutLocked });
    };
    updateLocator() {
        if (this.locator === undefined || this.grid == null) {
            return;
        }
        this.locator
            .setGrid(this.grid)
            .setNumFrozenRows(this.state.numFrozenRowsClamped)
            .setNumFrozenColumns(this.state.numFrozenColumnsClamped);
    }
    updateViewportRect = (nextViewportRect) => {
        if (nextViewportRect === undefined) {
            return;
        }
        const { viewportRect } = this.state;
        this.setState({ viewportRect: nextViewportRect });
        const didViewportChange = (viewportRect != null && !viewportRect.equals(nextViewportRect)) ||
            (viewportRect == null && nextViewportRect != null);
        if (didViewportChange) {
            this.invokeOnVisibleCellsChangeCallback(nextViewportRect);
        }
    };
    invokeOnVisibleCellsChangeCallback(viewportRect) {
        if (this.grid == null) {
            return;
        }
        const columnIndices = this.grid.getColumnIndicesInRect(viewportRect);
        const rowIndices = this.grid.getRowIndicesInRect({ rect: viewportRect });
        this.props.onVisibleCellsChange?.(rowIndices, columnIndices);
    }
    getMaxFrozenColumnIndex = () => {
        return this.state.numFrozenColumnsClamped - 1;
    };
    getMaxFrozenRowIndex = () => {
        return this.state.numFrozenRowsClamped - 1;
    };
    /**
     * Normalizes RenderMode.BATCH_ON_UPDATE into RenderMode.{BATCH,NONE}. We do
     * this because there are actually multiple updates required before the
     * <Table> is considered fully "mounted," and adding that knowledge to child
     * components would lead to tight coupling. Thus, keep it simple for them.
     */
    getNormalizedRenderMode() {
        const { renderMode } = this.props;
        const shouldBatchRender = renderMode === renderMode_1.RenderMode.BATCH || (renderMode === renderMode_1.RenderMode.BATCH_ON_UPDATE && this.didCompletelyMount);
        return shouldBatchRender ? renderMode_1.RenderMode.BATCH : renderMode_1.RenderMode.NONE;
    }
    handleColumnResizeGuide = (verticalGuides) => {
        this.setState({ verticalGuides });
    };
    handleRowResizeGuide = (horizontalGuides) => {
        this.setState({ horizontalGuides });
    };
    getHeaderDimensions = () => {
        return {
            columnHeaderHeight: this.getColumnHeaderHeight(),
            rowHeaderWidth: this.getRowHeaderWidth(),
        };
    };
    getColumnHeaderHeight = () => {
        return this.props.enableColumnHeader ? this.columnHeaderHeight : 0;
    };
    getRowHeaderWidth = () => {
        return this.props.enableRowHeader ? this.rowHeaderWidth : 0;
    };
}
exports.Table = Table;
/** @deprecated Use `Table` instead */
exports.Table2 = Table;
//# sourceMappingURL=table.js.map