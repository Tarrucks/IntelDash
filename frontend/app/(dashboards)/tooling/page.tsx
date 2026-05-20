"use client";

import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api, ApiError, type OsintNode } from "@/lib/api";

export default function ToolingLibraryPage() {
  const [tree, setTree] = useState<OsintNode | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.tooling
      .tree()
      .then(setTree)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load tree"));
  }, []);

  const filtered = useMemo(() => {
    if (!tree) return null;
    if (!query.trim()) return tree;
    return filterTree(tree, query.toLowerCase()) ?? emptyTree();
  }, [tree, query]);

  return (
    <div className="space-y-3">
      <header>
        <span
          className="inline-block h-2 w-2 rounded-full bg-domain-case align-middle"
          aria-hidden
        />
        <h1 className="ml-2 inline align-middle text-lg font-semibold">Tooling Library</h1>
        <p className="mt-1 text-xs text-fg-muted">
          Mirror of the{" "}
          <a
            href="https://github.com/lockfale/OSINT-Framework"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-fg"
          >
            OSINT Framework
          </a>{" "}
          taxonomy. Click any leaf to open the upstream tool.
        </p>
      </header>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Filter by name, URL, or tag…"
        className="input"
        aria-label="Filter taxonomy"
      />

      {error && (
        <div role="alert" className="rounded-md border border-red-900/60 bg-red-950/40 p-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {filtered && (
        <div className="surface max-h-[60vh] overflow-y-auto p-2 text-xs">
          <TreeNode node={filtered} depth={0} initiallyOpen />
        </div>
      )}
    </div>
  );
}

function TreeNode({
  node,
  depth,
  initiallyOpen = false,
}: {
  node: OsintNode;
  depth: number;
  initiallyOpen?: boolean;
}) {
  const [open, setOpen] = useState(initiallyOpen || depth < 1);

  if (node.type === "url") {
    return (
      <a
        href={node.url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-2 rounded px-2 py-1 text-fg-muted hover:bg-bg-elevated hover:text-fg"
        style={{ paddingLeft: depth * 12 + 24 }}
      >
        <ExternalLink size={12} className="shrink-0 text-fg-subtle" />
        <span className="truncate">{node.name}</span>
        {node.tags.length > 0 && (
          <span className="ml-auto truncate text-[10px] text-fg-subtle">
            {node.tags.join(", ")}
          </span>
        )}
      </a>
    );
  }

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1 rounded px-2 py-1 text-left text-fg hover:bg-bg-elevated"
        style={{ paddingLeft: depth * 12 + 4 }}
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="font-medium">{node.name}</span>
        <span className="ml-auto text-[10px] text-fg-subtle">
          {node.children.length}
        </span>
      </button>
      {open && (
        <div>
          {node.children.map((c, idx) => (
            <TreeNode
              key={`${c.name}-${idx}`}
              node={c}
              depth={depth + 1}
              initiallyOpen={initiallyOpen && depth === 0}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/** Returns a new tree pruned to nodes that match the needle, or null
 * if nothing matched. Folders are kept if any descendant matches. */
function filterTree(node: OsintNode, needle: string): OsintNode | null {
  if (node.type === "url") {
    const hit =
      node.name.toLowerCase().includes(needle) ||
      node.url.toLowerCase().includes(needle) ||
      node.tags.some((t) => t.toLowerCase().includes(needle));
    return hit ? node : null;
  }
  const kept = node.children
    .map((c) => filterTree(c, needle))
    .filter((c): c is OsintNode => c !== null);
  if (kept.length === 0) return null;
  return { ...node, children: kept };
}

function emptyTree(): OsintNode {
  return { name: "No matches", type: "folder", children: [] };
}
