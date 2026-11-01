import { type HeadingNode, type PageNode } from "@documentalist/client";
/**
 * Performs an in-order traversal of the layout tree, invoking the callback for each node.
 * Callback receives an array of ancestors with direct parent first in the list.
 */
export declare function eachLayoutNode(layout: Array<HeadingNode | PageNode>, callback: (node: HeadingNode | PageNode, parents: PageNode[]) => void, parents?: PageNode[]): void;
