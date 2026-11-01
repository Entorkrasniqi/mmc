"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TableQuadrantStack = void 0;
const tslib_1 = require("tslib");
const jsx_runtime_1 = require("react/jsx-runtime");
/*
 * Copyright 2017 Palantir Technologies, Inc. All rights reserved.
 *
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
const core_1 = require("@blueprintjs/core");
const Classes = tslib_1.__importStar(require("../common/classes"));
const grid_1 = require("../common/grid");
const ScrollUtils = tslib_1.__importStar(require("../common/internal/scrollUtils"));
const utils_1 = require("../common/utils");
const tableQuadrant_1 = require("./tableQuadrant");
const tableQuadrantStackCache_1 = require("./tableQuadrantStackCache");
// the debounce delay for updating the view on scroll. elements will be resized
// and rejiggered once scroll has ceased for at least this long, but not before.
const DEFAULT_VIEW_SYNC_DELAY = 500;
// if there are no frozen rows or columns, we still want the quadrant to be 1px
// bigger to reveal the header border. this border leaks into the cell grid to
// ensure that selection overlay borders (e.g.) will be perfectly flush with it.
const QUADRANT_MIN_SIZE = 1;
// a list of props that trigger layout changes. when these props change,
// quadrant views need to be explicitly resynchronized.
const SYNC_TRIGGER_PROP_KEYS = [
    "enableRowHeader",
    "loadingOptions",
    "numFrozenColumns",
    "numFrozenRows",
    "numColumns",
    "numRows",
    "enableColumnInteractionBar",
    "didHeadersMount",
    "enableColumnHeader",
];
class TableQuadrantStack extends core_1.AbstractComponent {
    // we want the user to explicitly pass a quadrantType. define defaultProps as a Partial to avoid
    // declaring that and other required props here.
    static defaultProps = {
        enableColumnHeader: true,
        enableColumnInteractionBar: undefined,
        enableRowHeader: true,
        isHorizontalScrollDisabled: false,
        isVerticalScrollDisabled: false,
        throttleScrolling: true,
        viewSyncDelay: DEFAULT_VIEW_SYNC_DELAY,
    };
    // Instance variables
    // ==================
    quadrantRefs = {
        [tableQuadrant_1.QuadrantType.MAIN]: {},
        [tableQuadrant_1.QuadrantType.TOP]: {},
        [tableQuadrant_1.QuadrantType.LEFT]: {},
        [tableQuadrant_1.QuadrantType.TOP_LEFT]: {},
    };
    quadrantRefHandlers = {
        [tableQuadrant_1.QuadrantType.MAIN]: this.generateQuadrantRefHandlers(tableQuadrant_1.QuadrantType.MAIN),
        [tableQuadrant_1.QuadrantType.TOP]: this.generateQuadrantRefHandlers(tableQuadrant_1.QuadrantType.TOP),
        [tableQuadrant_1.QuadrantType.LEFT]: this.generateQuadrantRefHandlers(tableQuadrant_1.QuadrantType.LEFT),
        [tableQuadrant_1.QuadrantType.TOP_LEFT]: this.generateQuadrantRefHandlers(tableQuadrant_1.QuadrantType.TOP_LEFT),
    };
    // this flag helps us avoid redundant work in the MAIN quadrant's onScroll callback, if the
    // callback was triggered from a manual scrollTop/scrollLeft update within an onWheel.
    wasMainQuadrantScrollTriggeredByWheelEvent = false;
    // keep throttled event callbacks around as instance variables, so we don't
    // have to continually reinstantiate them.
    throttledHandleMainQuadrantScroll;
    throttledHandleWheel;
    // cancel function for the debounced view sync handler
    cancelPendingViewSync;
    cache;
    // Public
    // ======
    constructor(props) {
        super(props);
        // callbacks trigger too frequently unless we throttle scroll and wheel
        // events. declare these functions on the component instance since
        // they're stateful.
        this.throttledHandleMainQuadrantScroll = core_1.Utils.throttleReactEventCallback(this.handleMainQuadrantScroll);
        this.throttledHandleWheel = core_1.Utils.throttleReactEventCallback(this.handleWheel);
        this.cache = new tableQuadrantStackCache_1.TableQuadrantStackCache();
    }
    /**
     * Scroll the main quadrant to the specified scroll offset, keeping all other quadrants in sync.
     */
    scrollToPosition(scrollLeft, scrollTop) {
        const { scrollContainer } = this.quadrantRefs[tableQuadrant_1.QuadrantType.MAIN];
        if (scrollContainer == null) {
            return;
        }
        this.wasMainQuadrantScrollTriggeredByWheelEvent = false;
        // this will trigger the main quadrant's scroll callback below
        scrollContainer.scrollLeft = scrollLeft;
        scrollContainer.scrollTop = scrollTop;
        this.syncQuadrantViews();
    }
    /**
     * Synchronizes quadrant sizes and scroll offsets based on the current
     * column, row, and header sizes. Useful for correcting quadrant sizes after
     * explicitly resizing columns and rows, for instance.
     *
     * Invoking this method imperatively is cheaper than providing columnWidths
     * or rowHeights array props to TableQuadrantStack and forcing it to run
     * expensive array diffs upon every update.
     */
    synchronizeQuadrantViews() {
        this.syncQuadrantViews();
    }
    componentDidMount() {
        this.emitRefs();
        this.syncQuadrantViews();
    }
    componentDidUpdate(prevProps) {
        if (
        // sync'ing quadrant views triggers expensive reflows, so we only call
        // it when layout-affecting props change.
        !core_1.Utils.shallowCompareKeys(this.props, prevProps, {
            include: SYNC_TRIGGER_PROP_KEYS,
        }) ||
            // in addition to those props, we also care about frozen parts of the grid
            // which may cause the top / left quadrants to change height / width
            this.didFrozenColumnWidthsChange(prevProps) ||
            this.didFrozenRowHeightsChange(prevProps)) {
            this.emitRefs();
            this.syncQuadrantViews();
        }
    }
    render() {
        const { grid, enableRowHeader, bodyRenderer, throttleScrolling, enableColumnHeader } = this.props;
        // use the more generic "scroll" event for the main quadrant to capture
        // *both* scrollbar interactions and trackpad/mousewheel gestures.
        const onMainQuadrantScroll = throttleScrolling
            ? this.throttledHandleMainQuadrantScroll
            : this.handleMainQuadrantScroll;
        const onWheel = throttleScrolling ? this.throttledHandleWheel : this.handleWheel;
        const baseProps = {
            bodyRenderer,
            enableColumnHeader,
            enableRowHeader,
            grid,
            onWheel,
        };
        const shouldRenderLeftQuadrants = this.shouldRenderLeftQuadrants();
        const maybeLeftQuadrant = shouldRenderLeftQuadrants ? ((0, jsx_runtime_1.jsx)(tableQuadrant_1.TableQuadrant, { ...baseProps, quadrantRef: this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.LEFT].quadrant, quadrantType: tableQuadrant_1.QuadrantType.LEFT, columnHeaderCellRenderer: this.renderLeftQuadrantColumnHeader, menuRenderer: this.renderLeftQuadrantMenu, rowHeaderCellRenderer: this.renderLeftQuadrantRowHeader, scrollContainerRef: this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.LEFT].scrollContainer })) : undefined;
        const maybeTopLeftQuadrant = shouldRenderLeftQuadrants ? ((0, jsx_runtime_1.jsx)(tableQuadrant_1.TableQuadrant, { ...baseProps, quadrantRef: this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.TOP_LEFT].quadrant, quadrantType: tableQuadrant_1.QuadrantType.TOP_LEFT, columnHeaderCellRenderer: this.renderTopLeftQuadrantColumnHeader, menuRenderer: this.renderTopLeftQuadrantMenu, rowHeaderCellRenderer: this.renderTopLeftQuadrantRowHeader, scrollContainerRef: this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.TOP_LEFT].scrollContainer })) : undefined;
        return ((0, jsx_runtime_1.jsxs)("div", { className: Classes.TABLE_QUADRANT_STACK, children: [this.renderTableOverlay(), (0, jsx_runtime_1.jsx)(tableQuadrant_1.TableQuadrant, { ...baseProps, bodyRef: this.props.bodyRef, onScroll: onMainQuadrantScroll, quadrantRef: this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.MAIN].quadrant, quadrantType: tableQuadrant_1.QuadrantType.MAIN, columnHeaderCellRenderer: this.renderMainQuadrantColumnHeader, menuRenderer: this.renderMainQuadrantMenu, rowHeaderCellRenderer: this.renderMainQuadrantRowHeader, scrollContainerRef: this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.MAIN].scrollContainer }), (0, jsx_runtime_1.jsx)(tableQuadrant_1.TableQuadrant, { ...baseProps, quadrantRef: this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.TOP].quadrant, quadrantType: tableQuadrant_1.QuadrantType.TOP, columnHeaderCellRenderer: this.renderTopQuadrantColumnHeader, menuRenderer: this.renderTopQuadrantMenu, rowHeaderCellRenderer: this.renderTopQuadrantRowHeader, scrollContainerRef: this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.TOP].scrollContainer }), maybeLeftQuadrant, maybeTopLeftQuadrant] }));
    }
    // Ref handlers
    // ============
    generateQuadrantRefHandlers(quadrantType) {
        const reducer = (agg, key) => {
            agg[key] = (ref) => (this.quadrantRefs[quadrantType][key] = ref);
            return agg;
        };
        const refHandlers = [
            "columnHeader",
            "menu",
            "quadrant",
            "rowHeader",
            "scrollContainer",
        ];
        return refHandlers.reduce(reducer, {});
    }
    // Scrolling overlay renderer
    // ===========================
    renderTableOverlay = () => {
        const columnHeaderHeight = this.cache.getColumnHeaderHeight();
        const mainScrollContainer = this.quadrantRefs[tableQuadrant_1.QuadrantType.MAIN].scrollContainer;
        const scrollBarWidth = ScrollUtils.measureScrollBarThickness(mainScrollContainer, "vertical");
        return this.props.renderScrollIndicatorOverlay?.(scrollBarWidth, columnHeaderHeight);
    };
    // Quadrant-specific renderers
    // ===========================
    // Menu
    renderMainQuadrantMenu = () => {
        return this.props.menuRenderer?.(this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.MAIN].menu);
    };
    renderTopQuadrantMenu = () => {
        return this.props.menuRenderer?.(this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.TOP].menu);
    };
    renderLeftQuadrantMenu = () => {
        return this.props.menuRenderer?.(this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.LEFT].menu);
    };
    renderTopLeftQuadrantMenu = () => {
        return this.props.menuRenderer?.(this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.TOP_LEFT].menu);
    };
    // Column header
    renderMainQuadrantColumnHeader = (showFrozenColumnsOnly) => {
        const refHandler = this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.MAIN].columnHeader;
        const resizeHandler = this.handleColumnResizeGuideMain;
        const reorderingHandler = this.handleColumnsReordering;
        if (refHandler === undefined) {
            return undefined;
        }
        return this.props.columnHeaderRenderer?.(refHandler, resizeHandler, reorderingHandler, showFrozenColumnsOnly);
    };
    renderTopQuadrantColumnHeader = (showFrozenColumnsOnly) => {
        const refHandler = this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.TOP].columnHeader;
        const resizeHandler = this.handleColumnResizeGuideTop;
        const reorderingHandler = this.handleColumnsReordering;
        if (refHandler === undefined) {
            return undefined;
        }
        return this.props.columnHeaderRenderer?.(refHandler, resizeHandler, reorderingHandler, showFrozenColumnsOnly);
    };
    renderLeftQuadrantColumnHeader = (showFrozenColumnsOnly) => {
        const refHandler = this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.LEFT].columnHeader;
        const resizeHandler = this.handleColumnResizeGuideLeft;
        const reorderingHandler = this.handleColumnsReordering;
        if (refHandler === undefined) {
            return undefined;
        }
        return this.props.columnHeaderRenderer?.(refHandler, resizeHandler, reorderingHandler, showFrozenColumnsOnly);
    };
    renderTopLeftQuadrantColumnHeader = (showFrozenColumnsOnly) => {
        const refHandler = this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.TOP_LEFT].columnHeader;
        const resizeHandler = this.handleColumnResizeGuideTopLeft;
        const reorderingHandler = this.handleColumnsReordering;
        if (refHandler === undefined) {
            return undefined;
        }
        return this.props.columnHeaderRenderer?.(refHandler, resizeHandler, reorderingHandler, showFrozenColumnsOnly);
    };
    // Row header
    renderMainQuadrantRowHeader = (showFrozenRowsOnly) => {
        const refHandler = this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.MAIN].rowHeader;
        if (refHandler === undefined) {
            return undefined;
        }
        return this.props.rowHeaderRenderer?.(refHandler, this.handleRowResizeGuideMain, this.handleRowsReordering, showFrozenRowsOnly);
    };
    renderTopQuadrantRowHeader = (showFrozenRowsOnly) => {
        const refHandler = this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.TOP].rowHeader;
        if (refHandler === undefined) {
            return undefined;
        }
        return this.props.rowHeaderRenderer?.(refHandler, this.handleRowResizeGuideTop, this.handleRowsReordering, showFrozenRowsOnly);
    };
    renderLeftQuadrantRowHeader = (showFrozenRowsOnly) => {
        const refHandler = this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.LEFT].rowHeader;
        if (refHandler === undefined) {
            return undefined;
        }
        return this.props.rowHeaderRenderer?.(refHandler, this.handleRowResizeGuideLeft, this.handleRowsReordering, showFrozenRowsOnly);
    };
    renderTopLeftQuadrantRowHeader = (showFrozenRowsOnly) => {
        const refHandler = this.quadrantRefHandlers[tableQuadrant_1.QuadrantType.TOP_LEFT].rowHeader;
        if (refHandler === undefined) {
            return undefined;
        }
        return this.props.rowHeaderRenderer?.(refHandler, this.handleRowResizeGuideTopLeft, this.handleRowsReordering, showFrozenRowsOnly);
    };
    // Event handlers
    // ==============
    // Scrolling
    // ---------
    handleMainQuadrantScroll = (event) => {
        if (this.wasMainQuadrantScrollTriggeredByWheelEvent) {
            this.wasMainQuadrantScrollTriggeredByWheelEvent = false;
            return;
        }
        const mainScrollContainer = this.quadrantRefs[tableQuadrant_1.QuadrantType.MAIN].scrollContainer;
        if (mainScrollContainer == null) {
            return;
        }
        // invoke onScroll - which may read current scroll position - before
        // forcing a reflow with upcoming .scroll{Top,Left} setters.
        this.props.onScroll?.(event);
        // batch DOM reads here. note that onScroll events don't include deltas
        // like onWheel events do, so we have to read from the DOM directly.
        const nextScrollLeft = mainScrollContainer.scrollLeft;
        const nextScrollTop = mainScrollContainer.scrollTop;
        // with the "scroll" event, scroll offsets are updated prior to the
        // event's firing, so no explicit update needed.
        this.handleScrollOffsetChange("scrollLeft", nextScrollLeft);
        this.handleScrollOffsetChange("scrollTop", nextScrollTop);
        // sync less important view stuff when scrolling/wheeling stops.
        this.syncQuadrantViewsDebounced();
    };
    handleWheel = (event) => {
        // again, let the listener read the current scroll position before we
        // force a reflow by resizing or repositioning stuff.
        this.props.onScroll?.(event);
        // this helper performs DOM reads, so do them together before the writes below.
        const nextScrollLeft = this.getNextScrollOffset("horizontal", event.deltaX);
        const nextScrollTop = this.getNextScrollOffset("vertical", event.deltaY);
        // update this flag before updating the main quadrant scroll offsets,
        // since we need this set before onScroll fires.
        if (nextScrollLeft != null || nextScrollTop != null) {
            this.wasMainQuadrantScrollTriggeredByWheelEvent = true;
        }
        // manually update the affected quadrant's scroll position to make sure
        // it stays perfectly in sync with dependent quadrants in each frame.
        // note: these DOM writes are batched together after the reads above.
        if (nextScrollLeft !== undefined) {
            this.quadrantRefs[tableQuadrant_1.QuadrantType.MAIN].scrollContainer.scrollLeft = nextScrollLeft;
            this.handleScrollOffsetChange("scrollLeft", nextScrollLeft);
        }
        if (nextScrollTop !== undefined) {
            this.quadrantRefs[tableQuadrant_1.QuadrantType.MAIN].scrollContainer.scrollTop = nextScrollTop;
            this.handleScrollOffsetChange("scrollTop", nextScrollTop);
        }
        // sync less important view stuff when scrolling/wheeling stops.
        this.syncQuadrantViewsDebounced();
    };
    getNextScrollOffset = (direction, delta) => {
        const { grid, isHorizontalScrollDisabled, isVerticalScrollDisabled } = this.props;
        const isHorizontal = direction === "horizontal";
        const scrollKey = isHorizontal ? "scrollLeft" : "scrollTop";
        const isScrollDisabled = isHorizontal ? isHorizontalScrollDisabled : isVerticalScrollDisabled;
        if (isScrollDisabled) {
            return undefined;
        }
        // measure client size on the first event of the current wheel gesture,
        // then grab cached values on successive events to eliminate DOM reads.
        // requires clearing the cached values in the debounced view-update at
        // the end of the wheel event.
        // ASSUMPTION: the client size won't change during the wheel event.
        let clientSize = isHorizontal
            ? this.cache.getScrollContainerClientWidth()
            : this.cache.getScrollContainerClientHeight();
        if (clientSize == null) {
            // should trigger only on the first scroll of the wheel gesture.
            // will save client width and height sizes in the cache.
            clientSize = this.updateScrollContainerClientSize(isHorizontal);
        }
        // By now, the client width and height will have been saved in cache, so
        // they can't be undefined anymore. Also, events can only happen after
        // mount, so we're guaranteed to have measured the header sizes in
        // syncQuadrantViews() by now too, as it's invoked on mount.
        const containerSize = isHorizontal
            ? this.cache.getScrollContainerClientWidth() - this.cache.getRowHeaderWidth()
            : this.cache.getScrollContainerClientHeight() - this.cache.getColumnHeaderHeight();
        const gridSize = isHorizontal ? grid.getWidth() : grid.getHeight();
        const maxScrollOffset = Math.max(0, gridSize - containerSize);
        const currScrollOffset = this.cache.getScrollOffset(scrollKey);
        const nextScrollOffset = core_1.Utils.clamp(currScrollOffset + delta, 0, maxScrollOffset);
        return nextScrollOffset;
    };
    // Resizing
    // --------
    // Columns
    handleColumnResizeGuideMain = (verticalGuides) => {
        this.invokeColumnResizeHandler(verticalGuides, tableQuadrant_1.QuadrantType.MAIN);
    };
    handleColumnResizeGuideTop = (verticalGuides) => {
        this.invokeColumnResizeHandler(verticalGuides, tableQuadrant_1.QuadrantType.TOP);
    };
    handleColumnResizeGuideLeft = (verticalGuides) => {
        this.invokeColumnResizeHandler(verticalGuides, tableQuadrant_1.QuadrantType.LEFT);
    };
    handleColumnResizeGuideTopLeft = (verticalGuides) => {
        this.invokeColumnResizeHandler(verticalGuides, tableQuadrant_1.QuadrantType.TOP_LEFT);
    };
    invokeColumnResizeHandler = (verticalGuides, quadrantType) => {
        const adjustedGuides = this.adjustVerticalGuides(verticalGuides, quadrantType);
        this.props.handleColumnResizeGuide?.(adjustedGuides);
    };
    // Rows
    handleRowResizeGuideMain = (horizontalGuides) => {
        this.invokeRowResizeHandler(horizontalGuides, tableQuadrant_1.QuadrantType.MAIN);
    };
    handleRowResizeGuideTop = (horizontalGuides) => {
        this.invokeRowResizeHandler(horizontalGuides, tableQuadrant_1.QuadrantType.TOP);
    };
    handleRowResizeGuideLeft = (horizontalGuides) => {
        this.invokeRowResizeHandler(horizontalGuides, tableQuadrant_1.QuadrantType.LEFT);
    };
    handleRowResizeGuideTopLeft = (horizontalGuides) => {
        this.invokeRowResizeHandler(horizontalGuides, tableQuadrant_1.QuadrantType.TOP_LEFT);
    };
    invokeRowResizeHandler = (horizontalGuides, quadrantType) => {
        const adjustedGuides = this.adjustHorizontalGuides(horizontalGuides, quadrantType);
        this.props.handleRowResizeGuide?.(adjustedGuides);
    };
    // Reordering
    // ----------
    // Columns
    handleColumnsReordering = (oldIndex, newIndex, length) => {
        const guideIndex = utils_1.Utils.reorderedIndexToGuideIndex(oldIndex, newIndex, length);
        const leftOffset = this.props.grid.getCumulativeWidthBefore(guideIndex);
        const { numFrozenColumns = 0 } = this.props;
        const quadrantType = guideIndex <= numFrozenColumns ? tableQuadrant_1.QuadrantType.TOP_LEFT : tableQuadrant_1.QuadrantType.TOP;
        const verticalGuides = this.adjustVerticalGuides([leftOffset], quadrantType);
        this.props.handleColumnsReordering?.(verticalGuides);
    };
    // Rows
    handleRowsReordering = (oldIndex, newIndex, length) => {
        const guideIndex = utils_1.Utils.reorderedIndexToGuideIndex(oldIndex, newIndex, length);
        const topOffset = this.props.grid.getCumulativeHeightBefore(guideIndex);
        const { numFrozenRows = 0 } = this.props;
        const quadrantType = guideIndex <= numFrozenRows ? tableQuadrant_1.QuadrantType.TOP_LEFT : tableQuadrant_1.QuadrantType.LEFT;
        const horizontalGuides = this.adjustHorizontalGuides([topOffset], quadrantType);
        this.props.handleRowsReordering?.(horizontalGuides);
    };
    // Emitters
    // ========
    emitRefs() {
        (0, core_1.setRef)(this.props.quadrantRef, this.quadrantRefs[tableQuadrant_1.QuadrantType.MAIN].quadrant);
        (0, core_1.setRef)(this.props.rowHeaderRef, this.quadrantRefs[tableQuadrant_1.QuadrantType.MAIN].rowHeader);
        (0, core_1.setRef)(this.props.columnHeaderRef, this.quadrantRefs[tableQuadrant_1.QuadrantType.MAIN].columnHeader);
        (0, core_1.setRef)(this.props.scrollContainerRef, this.quadrantRefs[tableQuadrant_1.QuadrantType.MAIN].scrollContainer);
    }
    // Size syncing
    // ============
    syncQuadrantViewsDebounced = () => {
        const { viewSyncDelay } = this.props;
        if (viewSyncDelay < 0) {
            // update synchronously
            this.syncQuadrantViews();
        }
        else {
            // update asynchronously after a debounced delay
            this.cancelPendingViewSync?.();
            this.cancelPendingViewSync = this.setTimeout(this.syncQuadrantViews, viewSyncDelay);
        }
    };
    syncQuadrantViews = () => {
        const mainRefs = this.quadrantRefs[tableQuadrant_1.QuadrantType.MAIN];
        const mainScrollContainer = mainRefs.scrollContainer;
        //
        // Reads (batched to avoid DOM thrashing)
        //
        const rowHeaderWidth = this.measureDesiredRowHeaderWidth();
        const columnHeaderHeight = this.measureDesiredColumnHeaderHeight();
        const leftQuadrantGridWidth = this.getSecondaryQuadrantGridSize("width");
        const topQuadrantGridHeight = this.getSecondaryQuadrantGridSize("height");
        const leftQuadrantWidth = rowHeaderWidth + leftQuadrantGridWidth;
        const topQuadrantHeight = columnHeaderHeight + topQuadrantGridHeight;
        const rightScrollBarWidth = ScrollUtils.measureScrollBarThickness(mainScrollContainer, "vertical");
        const bottomScrollBarHeight = ScrollUtils.measureScrollBarThickness(mainScrollContainer, "horizontal");
        // if columnHeader is enabled, ensure neither of these measurements confusingly clamps to zero height.
        const adjustedColumnHeaderHeight = this.maybeIncreaseToMinColHeaderHeight(columnHeaderHeight);
        const adjustedTopQuadrantHeight = this.maybeIncreaseToMinColHeaderHeight(topQuadrantHeight);
        // Update cache: let's read now whatever values we might need later.
        // prevents unnecessary reflows in the future.
        this.cache.setRowHeaderWidth(rowHeaderWidth);
        this.cache.setColumnHeaderHeight(columnHeaderHeight);
        // ...however, we also clear the cached client size, so we can read it
        // again when a new scroll begins. not safe to assume this won't change.
        // TODO: maybe use the ResizeSensor?
        this.cache.setScrollContainerClientWidth(undefined);
        this.cache.setScrollContainerClientHeight(undefined);
        //
        // Writes (batched to avoid DOM thrashing)
        //
        // Quadrant-size sync'ing: make the quadrants precisely as big as they
        // need to be to fit their variable-sized headers and/or frozen areas.
        this.maybesSetQuadrantRowHeaderSizes(rowHeaderWidth);
        this.maybeSetQuadrantMenuElementSizes(rowHeaderWidth, adjustedColumnHeaderHeight);
        this.maybeSetQuadrantSizes(leftQuadrantWidth, adjustedTopQuadrantHeight);
        // Scrollbar clearance: tweak the quadrant bottom/right offsets to
        // reveal the MAIN-quadrant scrollbars if they're visible.
        this.maybeSetQuadrantPositionOffset(tableQuadrant_1.QuadrantType.TOP, "right", rightScrollBarWidth);
        this.maybeSetQuadrantPositionOffset(tableQuadrant_1.QuadrantType.LEFT, "bottom", bottomScrollBarHeight);
        // Scroll syncing: sync the scroll offsets of quadrants that may or may
        // not have been around prior to this update.
        this.maybeSetQuadrantScrollOffset(tableQuadrant_1.QuadrantType.LEFT, "scrollTop");
        this.maybeSetQuadrantScrollOffset(tableQuadrant_1.QuadrantType.TOP, "scrollLeft");
    };
    maybeSetQuadrantSizes = (width, height) => {
        const leftWidth = utils_1.Utils.clamp(width, this.props.enableRowHeader ? grid_1.Grid.MIN_ROW_HEADER_WIDTH : 0);
        const topHeight = utils_1.Utils.clamp(height, this.props.enableColumnHeader ? grid_1.Grid.MIN_COLUMN_HEADER_HEIGHT : 0);
        this.maybesSetQuadrantSize(tableQuadrant_1.QuadrantType.LEFT, "width", leftWidth);
        this.maybesSetQuadrantSize(tableQuadrant_1.QuadrantType.TOP, "height", topHeight);
        this.maybesSetQuadrantSize(tableQuadrant_1.QuadrantType.TOP_LEFT, "width", leftWidth);
        this.maybesSetQuadrantSize(tableQuadrant_1.QuadrantType.TOP_LEFT, "height", topHeight);
    };
    maybesSetQuadrantSize = (quadrantType, dimension, value) => {
        const { quadrant } = this.quadrantRefs[quadrantType];
        if (quadrant != null) {
            quadrant.style[dimension] = `${value}px`;
        }
    };
    maybeSetQuadrantPositionOffset = (quadrantType, side, value) => {
        const { quadrant } = this.quadrantRefs[quadrantType];
        if (quadrant != null) {
            quadrant.style[side] = `${value}px`;
        }
    };
    maybesSetQuadrantRowHeaderSizes = (width) => {
        const rowHeaderWidth = utils_1.Utils.clamp(width, this.props.enableRowHeader ? grid_1.Grid.MIN_ROW_HEADER_WIDTH : 0);
        this.maybeSetQuadrantRowHeaderSize(tableQuadrant_1.QuadrantType.MAIN, rowHeaderWidth);
        this.maybeSetQuadrantRowHeaderSize(tableQuadrant_1.QuadrantType.TOP, rowHeaderWidth);
        this.maybeSetQuadrantRowHeaderSize(tableQuadrant_1.QuadrantType.LEFT, rowHeaderWidth);
        this.maybeSetQuadrantRowHeaderSize(tableQuadrant_1.QuadrantType.TOP_LEFT, rowHeaderWidth);
    };
    maybeSetQuadrantRowHeaderSize = (quadrantType, width) => {
        const { rowHeader } = this.quadrantRefs[quadrantType];
        if (rowHeader != null) {
            rowHeader.style.width = `${width}px`;
        }
    };
    maybeSetQuadrantMenuElementSizes = (width, height) => {
        const rowHeaderWidth = utils_1.Utils.clamp(width, this.props.enableRowHeader ? grid_1.Grid.MIN_ROW_HEADER_WIDTH : 0);
        this.maybeSetQuadrantMenuElementSize(tableQuadrant_1.QuadrantType.MAIN, rowHeaderWidth, height);
        this.maybeSetQuadrantMenuElementSize(tableQuadrant_1.QuadrantType.TOP, rowHeaderWidth, height);
        this.maybeSetQuadrantMenuElementSize(tableQuadrant_1.QuadrantType.LEFT, rowHeaderWidth, height);
        this.maybeSetQuadrantMenuElementSize(tableQuadrant_1.QuadrantType.TOP_LEFT, rowHeaderWidth, height);
    };
    maybeSetQuadrantMenuElementSize = (quadrantType, width, height) => {
        const { menu } = this.quadrantRefs[quadrantType];
        if (menu != null) {
            menu.style.width = `${width}px`;
            menu.style.height = `${height}px`;
        }
    };
    maybeSetQuadrantScrollOffset = (quadrantType, scrollKey, newOffset) => {
        const { scrollContainer } = this.quadrantRefs[quadrantType];
        const scrollOffset = newOffset != null ? newOffset : this.cache.getScrollOffset(scrollKey);
        if (scrollContainer != null) {
            scrollContainer[scrollKey] = scrollOffset;
        }
    };
    handleScrollOffsetChange = (scrollKey, offset) => {
        this.cache.setScrollOffset(scrollKey, offset);
        const dependentQuadrantType = scrollKey === "scrollLeft" ? tableQuadrant_1.QuadrantType.TOP : tableQuadrant_1.QuadrantType.LEFT;
        this.maybeSetQuadrantScrollOffset(dependentQuadrantType, scrollKey);
    };
    // this function is named 'update' instead of 'set', because a 'set'
    // function typically takes the new value as a parameter. we avoid that to
    // keep the isHorizontal logic tree contained within this function.
    updateScrollContainerClientSize(isHorizontal) {
        const mainScrollContainer = this.quadrantRefs[tableQuadrant_1.QuadrantType.MAIN].scrollContainer;
        if (isHorizontal) {
            this.cache.setScrollContainerClientWidth(mainScrollContainer?.clientWidth);
            return this.cache.getScrollContainerClientWidth();
        }
        else {
            this.cache.setScrollContainerClientHeight(mainScrollContainer?.clientHeight);
            return this.cache.getScrollContainerClientHeight();
        }
    }
    maybeIncreaseToMinColHeaderHeight(height) {
        if (this.props.enableColumnHeader) {
            return height <= QUADRANT_MIN_SIZE ? grid_1.Grid.MIN_COLUMN_HEADER_HEIGHT : height;
        }
        else {
            return height;
        }
    }
    // Helpers
    // =======
    /** Returns true the cumulative width of all frozen columns in the grid changed. */
    didFrozenColumnWidthsChange(prevProps) {
        return (this.props.numFrozenColumns > 0 &&
            this.props.grid !== prevProps.grid &&
            this.props.grid.getCumulativeWidthAt(this.props.numFrozenColumns - 1) !==
                prevProps.grid.getCumulativeWidthAt(prevProps.numFrozenColumns - 1));
    }
    /** Returns true the cumulative height of all frozen rows in the grid changed. */
    didFrozenRowHeightsChange(prevProps) {
        return (this.props.numFrozenRows > 0 &&
            this.props.grid !== prevProps.grid &&
            this.props.grid.getCumulativeHeightAt(this.props.numFrozenRows - 1) !==
                prevProps.grid.getCumulativeHeightAt(prevProps.numFrozenRows - 1));
    }
    /**
     * Returns the width or height of *only the grid* in the secondary quadrants
     * (TOP, LEFT, TOP_LEFT), based on the number of frozen rows and columns.
     */
    getSecondaryQuadrantGridSize(dimension) {
        const { grid, numFrozenColumns, numFrozenRows } = this.props;
        const numFrozen = (dimension === "width" ? numFrozenColumns : numFrozenRows) ?? 0;
        const getterFn = dimension === "width" ? grid.getCumulativeWidthAt : grid.getCumulativeHeightAt;
        // both getter functions do O(1) lookups.
        return numFrozen > 0 ? getterFn(numFrozen - 1) : QUADRANT_MIN_SIZE;
    }
    /**
     * Measures the desired width of the row header based on its tallest
     * contents.
     */
    measureDesiredRowHeaderWidth() {
        // the MAIN row header serves as the source of truth
        const mainRowHeader = this.quadrantRefs[tableQuadrant_1.QuadrantType.MAIN].rowHeader;
        if (mainRowHeader == null) {
            return 0;
        }
        else {
            // (alas, we must force a reflow to measure the row header's "desired" width)
            mainRowHeader.style.width = "auto";
            return utils_1.Utils.clamp(mainRowHeader.clientWidth, grid_1.Grid.MIN_ROW_HEADER_WIDTH);
        }
    }
    /**
     * Measures the desired height of the column header based on its tallest
     * contents.
     */
    measureDesiredColumnHeaderHeight() {
        // unlike the row headers, the column headers are in a display-flex
        // layout and are not actually bound by any fixed `height` that we set,
        // so they'll grow freely to their necessary size. makes measuring easy!
        const mainColumnHeader = this.quadrantRefs[tableQuadrant_1.QuadrantType.MAIN].columnHeader;
        return mainColumnHeader == null ? 0 : utils_1.Utils.clamp(mainColumnHeader.clientHeight, grid_1.Grid.MIN_COLUMN_HEADER_HEIGHT);
    }
    shouldRenderLeftQuadrants(props = this.props) {
        const { enableRowHeader, numFrozenColumns } = props;
        return enableRowHeader || (numFrozenColumns != null && numFrozenColumns > 0);
    }
    // Resizing
    // should return empty array [] if we just finished resizing
    adjustVerticalGuides(verticalGuides, quadrantType) {
        const isFrozenQuadrant = quadrantType === tableQuadrant_1.QuadrantType.LEFT || quadrantType === tableQuadrant_1.QuadrantType.TOP_LEFT;
        const scrollAmount = isFrozenQuadrant ? 0 : this.cache.getScrollOffset("scrollLeft");
        const rowHeaderWidth = this.cache.getRowHeaderWidth();
        return verticalGuides?.map(verticalGuide => verticalGuide - scrollAmount + rowHeaderWidth) ?? [];
    }
    // should return empty array [] if we just finished resizing
    adjustHorizontalGuides(horizontalGuides, quadrantType) {
        const isFrozenQuadrant = quadrantType === tableQuadrant_1.QuadrantType.TOP || quadrantType === tableQuadrant_1.QuadrantType.TOP_LEFT;
        const scrollAmount = isFrozenQuadrant ? 0 : this.cache.getScrollOffset("scrollTop");
        const columnHeaderHeight = this.cache.getColumnHeaderHeight();
        return horizontalGuides?.map(horizontalGuide => horizontalGuide - scrollAmount + columnHeaderHeight) ?? [];
    }
}
exports.TableQuadrantStack = TableQuadrantStack;
//# sourceMappingURL=tableQuadrantStack.js.map