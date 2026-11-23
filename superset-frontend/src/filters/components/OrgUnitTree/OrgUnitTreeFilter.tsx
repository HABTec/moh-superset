/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.
 *
 * Org Unit Tree filter — Superset Native Filter that renders the MoH
 * hierarchy as a tree picker. Selection is pending until the user clicks
 * Apply; that's when setDataMask fires and charts re-query.
 *
 * Maps the selected node's level to the existing dataset filter dimension:
 *
 *     Level 1 (Country)     → clear all org filters (show all)
 *     Level 2 (Region)      → region
 *     Level 3 (Zone)        → zone
 *     Level 4 (Woreda)      → woreda
 *     Level 5 (PHCU)        → phcu
 *     Level 6 (Health Post) → health_post
 *
 * CBMP coupling (no cascade-parent config required):
 * the tree watches any native filter named/columned like CBMP and calls
 * organisationUnits?cbmp_type=…. Empty CBMP selection → full tree.
 *
 * Search: typing two or more characters queries organisationUnits/search
 * across every level (the tree lazy-loads, so a client-side search would
 * only see expanded nodes). Matches are listed flat with their ancestors and
 * can be checked directly; selected units show as removable tags.
 *
 * Datasets are untouched — they continue to read filter_values('region') etc.
 */
import { NativeFilterType } from '@superset-ui/core';
import { t } from '@apache-superset/core/translation';
import { styled } from '@apache-superset/core/theme';
import {
  Checkbox,
  Input,
  Tag,
  Tree,
  type TreeDataNode,
} from '@superset-ui/core/components';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Key as ReactKey } from 'react';
import { useSelector } from 'react-redux';
import type { RootState } from 'src/dashboard/types';

import { useAssignedOrgUnit } from './useAssignedOrgUnit';
import type {
  OrgUnit,
  OrgUnitSelection,
  OrgUnitTreeFilterProps,
} from './types';

const LEVEL_TO_DIM: Record<number, string> = {
  2: 'region',
  3: 'zone',
  4: 'woreda',
  5: 'phcu',
  6: 'health_post',
};

const LEVEL_LABELS: Record<number, string> = {
  1: t('Country'),
  2: t('Region'),
  3: t('Zone'),
  4: t('Woreda'),
  5: t('PHCU'),
  6: t('Health post'),
};

/** Minimum characters before the server-side name search runs. */
export const SEARCH_MIN_CHARS = 2;
const SEARCH_DEBOUNCE_MS = 300;

const CBMP_COLUMN_NAMES = new Set(['cbmp_type', 'cbmp']);

function normalizeCol(col: unknown): string {
  return String(col || '')
    .toLowerCase()
    .replace(/\s+/g, '_');
}

function collectStringValues(raw: unknown): string[] {
  const values: string[] = [];
  if (Array.isArray(raw)) {
    for (const item of raw) {
      if (item != null && String(item).trim()) {
        values.push(String(item).trim());
      }
    }
  } else if (raw != null && String(raw).trim()) {
    values.push(String(raw).trim());
  }
  return values;
}

function isCbmpFilter(filter: {
  name?: string;
  filterType?: string;
  targets?: Array<{ column?: { name?: string; column_name?: string } }>;
}): boolean {
  if (filter.filterType === 'filter_org_unit_tree') {
    return false;
  }
  const name = String(filter.name || '').toLowerCase();
  if (name.includes('cbmp')) {
    return true;
  }
  return (filter.targets || []).some(target => {
    const col = normalizeCol(target.column?.name || target.column?.column_name);
    return CBMP_COLUMN_NAMES.has(col) || col.includes('cbmp');
  });
}

const Wrapper = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
`;

const TreeBox = styled.div`
  flex: 1;
  min-height: 240px;
  max-height: min(320px, 50vh);
  overflow: auto;
  border: 1px solid ${({ theme }) => theme.colorBorder};
  border-radius: 6px;
  padding: 6px 4px;
  background: ${({ theme }) => theme.colorBgContainer};
`;

const Toolbar = styled.div`
  display: flex;
  gap: 12px;
  padding: 4px 4px 6px;
  font-size: 12px;
  align-items: center;
  flex-wrap: wrap;
`;

const Status = styled.span`
  margin-left: auto;
  color: ${({ theme }) => theme.colorTextSecondary};
  font-size: 11px;
`;

const ToolbarLink = styled.button`
  background: none;
  border: none;
  padding: 0;
  color: ${({ theme }) => theme.colorPrimary};
  cursor: pointer;
  font-size: inherit;
  &:hover {
    text-decoration: underline;
  }
  &:disabled {
    color: ${({ theme }) => theme.colorTextDisabled};
    cursor: default;
    text-decoration: none;
  }
`;

/* Search, toolbar and selected tags stay visible while the list scrolls,
   including when the whole filter sits inside a scrolling popup. */
const StickyHeader = styled.div`
  position: sticky;
  top: 0;
  z-index: 1;
  padding-top: 2px;
  background: ${({ theme }) => theme.colorBgElevated};
`;

const SelectedTags = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  max-height: 96px;
  overflow-y: auto;
  padding: 0 4px 6px;
`;

const ResultRow = styled.label`
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 4px;
  border-radius: 4px;
  cursor: pointer;
  &:hover {
    background: ${({ theme }) => theme.colorFillTertiary};
  }
`;

const ErrorText = styled.div`
  color: ${({ theme }) => theme.colorError};
`;

const ResultMeta = styled.div`
  color: ${({ theme }) => theme.colorTextSecondary};
  font-size: 11px;
`;

/** "Region · Amhara › North Gondar" — level plus ancestor trail. */
export function describeSearchResult(unit: OrgUnit): string {
  const level = LEVEL_LABELS[unit.level] || t('Level %(n)s', { n: unit.level });
  const trail = (unit.ancestors || [])
    .map(a => (a.displayName || '').trim())
    .filter(Boolean)
    .join(' › ');
  return trail ? `${level} · ${trail}` : level;
}

function toSelection(u: OrgUnit): OrgUnitSelection {
  return {
    id: u.id,
    displayName: (u.displayName || '').trim() || u.id,
    level: u.level,
  };
}

/** Add or remove one unit, keeping every other selection untouched. */
export function toggleSelection(
  current: OrgUnitSelection[],
  unit: OrgUnitSelection,
  checked: boolean,
): OrgUnitSelection[] {
  const without = current.filter(s => s.id !== unit.id);
  return checked ? [...without, unit] : without;
}

type Node = TreeDataNode & {
  unit: OrgUnit;
  isLeaf?: boolean;
};

function toNode(u: OrgUnit, maxLevel: number): Node {
  return {
    key: u.id,
    title: (u.displayName || '').trim() || u.id,
    unit: u,
    isLeaf: u.level >= maxLevel,
    children: undefined, // populated lazily on expand
  };
}

function buildDataMask(sels: OrgUnitSelection[]) {
  if (!sels || sels.length === 0) {
    return {
      filterState: { value: null },
      extraFormData: { filters: [] },
    };
  }

  // Group selections by their dimension (level → region/zone/.../health_post).
  // Country (level 1) is the implicit "all" and contributes nothing.
  const byDim: Record<string, string[]> = {};
  const labels: string[] = [];
  for (const s of sels) {
    if (s.level <= 1) continue;
    const dim = LEVEL_TO_DIM[s.level];
    if (!dim) continue;
    (byDim[dim] = byDim[dim] || []).push(s.displayName);
    labels.push(s.displayName);
  }

  if (labels.length === 0) {
    return {
      filterState: { value: null },
      extraFormData: { filters: [] },
    };
  }

  // One filter clause per dimension. The dataset SQL reads each via
  // filter_values('region') / filter_values('zone') / etc.
  const filters = Object.entries(byDim).map(([col, val]) => ({
    col,
    op: 'IN',
    val,
  }));

  return {
    filterState: { value: labels },
    extraFormData: { filters },
  };
}

function patchChildren(nodes: Node[], key: string, kids: Node[]): Node[] {
  return nodes.map(n => {
    if (n.key === key) return { ...n, children: kids };
    if (n.children) {
      return { ...n, children: patchChildren(n.children as Node[], key, kids) };
    }
    return n;
  });
}

/** Read selected CBMP values from cascade parent filters in formData. */
export function getCbmpTypesFromFormData(formData: {
  extra_form_data?: { filters?: Array<{ col?: string; val?: unknown }> };
  extraFormData?: { filters?: Array<{ col?: string; val?: unknown }> };
}): string[] {
  const extra = formData.extra_form_data || formData.extraFormData || {};
  const filters = extra.filters || [];
  const values: string[] = [];
  for (const filter of filters) {
    const col = normalizeCol(filter.col);
    if (!CBMP_COLUMN_NAMES.has(col) && !col.includes('cbmp')) {
      continue;
    }
    values.push(...collectStringValues(filter.val));
  }
  return [...new Set(values)];
}

/**
 * Find CBMP selections from dashboard native filters + dataMask.
 * Used so Org Unit Tree works without configuring cascade parents.
 */
export function getCbmpTypesFromDashboard(
  filters: RootState['nativeFilters']['filters'] | undefined,
  dataMask: RootState['dataMask'] | undefined,
): string[] {
  if (!filters || !dataMask) {
    return [];
  }
  const values: string[] = [];
  Object.values(filters).forEach(filter => {
    if (!filter || filter.type !== NativeFilterType.NativeFilter) {
      return;
    }
    if (!isCbmpFilter(filter)) {
      return;
    }
    const mask = dataMask[filter.id];
    const extraFilters = mask?.extraFormData?.filters || [];
    if (extraFilters.length) {
      extraFilters.forEach(item => {
        if ('val' in item) {
          values.push(...collectStringValues(item.val));
        }
      });
      return;
    }
    values.push(...collectStringValues(mask?.filterState?.value));
  });
  return [...new Set(values)];
}

function withCbmpParams(url: string, cbmpTypes: string[]): string {
  if (!cbmpTypes.length) {
    return url;
  }
  const params = new URLSearchParams();
  // Preserve any existing query string on `url`.
  const [base, existing = ''] = url.split('?', 2);
  if (existing) {
    new URLSearchParams(existing).forEach((value, key) => {
      params.append(key, value);
    });
  }
  cbmpTypes.forEach(type => params.append('cbmp_type', type));
  const query = params.toString();
  return query ? `${base}?${query}` : base;
}

export default function OrgUnitTreeFilter({
  formData,
  filterState,
  setDataMask,
}: OrgUnitTreeFilterProps) {
  const apiBaseUrl = formData.apiBaseUrl || '/api/v1/moh/dhis2';
  const rootLevel = Number(formData.rootLevel || 2); // 2 = Region (matches MOH_ORG_UNITS_ROOT_LEVEL)
  const maxLevel = Number(formData.maxLevel || 6);
  // The API limits sub-national users to their assigned unit's subtree.
  const assignedUnit = useAssignedOrgUnit(true, apiBaseUrl);
  const scopeName =
    assignedUnit && assignedUnit.level > 1 ? assignedUnit.name : null;

  const nativeFilters = useSelector(
    (state: RootState) => state.nativeFilters?.filters,
  );
  const dataMask = useSelector((state: RootState) => state.dataMask);

  const cbmpTypes = useMemo(() => {
    // Prefer cascade-injected formData when configured; otherwise auto-detect
    // the CBMP native filter from dashboard state (no dependency UI needed).
    const fromCascade = getCbmpTypesFromFormData(formData);
    if (fromCascade.length) {
      return fromCascade;
    }
    return getCbmpTypesFromDashboard(nativeFilters, dataMask);
  }, [
    formData.extra_form_data,
    formData.extraFormData,
    nativeFilters,
    dataMask,
  ]);
  const cbmpKey = useMemo(() => [...cbmpTypes].sort().join('|'), [cbmpTypes]);

  const [treeData, setTreeData] = useState<Node[]>([]);
  // Rich objects (with id + level) live only in local state. setDataMask is
  // called immediately on every check change — Superset's native filter
  // sidebar provides the global Apply / Clear buttons, so the plugin no
  // longer needs its own pending/applied tracking or buttons.
  const [selected, setSelected] = useState<OrgUnitSelection[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // Track expanded nodes explicitly so a lazy-load (which patches new node
  // object references) doesn't cause antd Tree to auto-collapse the node.
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
  const previousCbmpKey = useRef<string | null>(null);

  // -- initial / CBMP-driven root fetch ------------------------------------
  useEffect(() => {
    // Skip re-fetching the root when the data source is unchanged and the
    // roots are already loaded. The effect can otherwise re-run on incidental
    // identity changes (e.g. setDataMask), which would replace `treeData` with
    // brand-new collapsed nodes and wipe the user's expanded state.
    if (
      previousCbmpKey.current !== null &&
      previousCbmpKey.current === cbmpKey &&
      treeData.length > 0
    ) {
      return;
    }

    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const url = withCbmpParams(
          `${apiBaseUrl}/organisationUnits?level=${rootLevel}`,
          cbmpTypes,
        );
        const r = await fetch(url, { credentials: 'same-origin' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        if (cancelled) return;
        setTreeData(
          (data.organisationUnits || []).map((u: OrgUnit) =>
            toNode(u, maxLevel),
          ),
        );
        setError(null);

        // When CBMP selection changes, drop org-unit checks that may no
        // longer exist in the narrowed tree. Skip the first mount so we
        // don't wipe a restored filterState.
        if (
          previousCbmpKey.current !== null &&
          previousCbmpKey.current !== cbmpKey
        ) {
          setSelected([]);
          setDataMask(buildDataMask([]));
        }
        previousCbmpKey.current = cbmpKey;
      } catch (e: any) {
        if (!cancelled) setError(e.message || 'Failed to load org units');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    apiBaseUrl,
    rootLevel,
    maxLevel,
    cbmpKey,
    cbmpTypes,
    treeData.length,
    setDataMask,
  ]);

  // -- lazy load on expand --------------------------------------------------
  const loadChildren = useCallback(
    async (node: Node): Promise<void> => {
      if (node.children && node.children.length > 0) return;
      try {
        const url = withCbmpParams(
          `${apiBaseUrl}/organisationUnits/${node.unit.id}`,
          cbmpTypes,
        );
        const r = await fetch(url, { credentials: 'same-origin' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        const kids: Node[] = (data.children || []).map((u: OrgUnit) =>
          toNode(u, maxLevel),
        );
        // Tree is uncontrolled w.r.t. children — patch by key
        setTreeData(prev => patchChildren(prev, node.key as string, kids));
      } catch (e: any) {
        setError(e.message || 'Failed to load children');
      }
    },
    [apiBaseUrl, maxLevel, cbmpTypes],
  );

  // -- server-side name search ---------------------------------------------
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<OrgUnit[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const trimmedQuery = query.trim();
  const isSearchMode = trimmedQuery.length >= SEARCH_MIN_CHARS;

  const handleQueryChange = useCallback((value: string) => {
    setQuery(value);
    // Show the spinner through the debounce, not only once the request starts.
    setSearching(value.trim().length >= SEARCH_MIN_CHARS);
  }, []);

  // Results are only rendered in search mode, so stale ones from an earlier
  // query never show once the box is cleared.
  useEffect(() => {
    if (!isSearchMode) return undefined;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const url = withCbmpParams(
          `${apiBaseUrl}/organisationUnits/search?q=${encodeURIComponent(
            trimmedQuery,
          )}`,
          cbmpKey ? cbmpKey.split('|') : [],
        );
        const r = await fetch(url, { credentials: 'same-origin' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        if (cancelled) return;
        setResults(data.organisationUnits || []);
        setSearchError(null);
      } catch (e) {
        if (!cancelled) {
          setSearchError(
            e instanceof Error ? e.message : t('Failed to search org units'),
          );
        }
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [apiBaseUrl, cbmpKey, isSearchMode, trimmedQuery]);

  // -- handlers -------------------------------------------------------------
  // Commit on every check change. Superset's native filter sidebar has its
  // own global Apply / Clear buttons that batch and dispatch dataMasks.
  const commit = useCallback(
    (next: OrgUnitSelection[]) => {
      setSelected(next);
      setDataMask(buildDataMask(next));
    },
    [setDataMask],
  );

  // Toggle only the clicked node: units picked from search results may not
  // be loaded in the tree, so rebuilding from the tree's checked nodes would
  // drop them.
  const onCheck = (_: unknown, info: { checked: boolean; node: Node }) => {
    if (!info.node?.unit) return;
    commit(
      toggleSelection(selected, toSelection(info.node.unit), info.checked),
    );
  };

  const checkedKeys = useMemo(() => selected.map(s => s.id), [selected]);
  const selectedIds = useMemo(() => new Set(checkedKeys), [checkedKeys]);

  const handleExpand = useCallback((keys: ReactKey[]) => {
    setExpandedKeys(keys.map(String));
  }, []);

  const allRootsChecked =
    treeData.length > 0 && treeData.every(n => selectedIds.has(n.unit.id));
  const allResultsChecked =
    results.length > 0 && results.every(u => selectedIds.has(u.id));

  // In search mode "Select all" adds every match to the selection; otherwise
  // it selects the tree's root units.
  const handleSelectAll = useCallback(() => {
    if (isSearchMode) {
      const missing = results
        .filter(u => !selectedIds.has(u.id))
        .map(toSelection);
      commit([...selected, ...missing]);
      return;
    }
    commit(treeData.filter(n => n.unit).map(n => toSelection(n.unit)));
  }, [isSearchMode, results, selectedIds, selected, treeData, commit]);

  const handleClearAll = useCallback(() => commit([]), [commit]);

  return (
    <Wrapper>
      <StickyHeader>
        <Input.Search
          allowClear
          size="small"
          value={query}
          onChange={e => handleQueryChange(e.target.value)}
          placeholder={t('Search org units (region, zone, woreda…)')}
          aria-label={t('Search org units')}
          loading={isSearchMode && searching}
        />
        <Toolbar>
          <ToolbarLink
            type="button"
            onClick={handleSelectAll}
            disabled={
              isSearchMode
                ? searching || results.length === 0 || allResultsChecked
                : loading || !!error || allRootsChecked
            }
          >
            {isSearchMode ? t('Select all matches') : t('Select all')}
          </ToolbarLink>
          <ToolbarLink
            type="button"
            onClick={handleClearAll}
            disabled={loading || selected.length === 0}
          >
            {t('Clear')}
          </ToolbarLink>
          <Status>
            {cbmpTypes.length
              ? t('CBMP: %(types)s · %(n)s roots', {
                  types: cbmpTypes.join(', '),
                  n: treeData.length,
                })
              : scopeName
                ? t('Within %(name)s · %(n)s roots', {
                    name: scopeName,
                    n: treeData.length,
                  })
                : t('All org units · %(n)s roots', { n: treeData.length })}
          </Status>
        </Toolbar>
        {selected.length > 0 && (
          <SelectedTags aria-label={t('Selected org units')}>
            {selected.map(s => (
              <Tag
                key={s.id}
                closable
                onClose={e => {
                  e.preventDefault();
                  commit(toggleSelection(selected, s, false));
                }}
                title={LEVEL_LABELS[s.level]}
              >
                {s.displayName}
              </Tag>
            ))}
          </SelectedTags>
        )}
      </StickyHeader>
      {isSearchMode && (
        <TreeBox role="list" aria-label={t('Search results')}>
          {searchError && <ErrorText>{searchError}</ErrorText>}
          {!searchError && !searching && results.length === 0 && (
            <div style={{ padding: 8, opacity: 0.7 }}>
              {t('No org units match "%(q)s"', { q: trimmedQuery })}
            </div>
          )}
          {!searchError &&
            results.map(u => (
              <ResultRow key={u.id} role="listitem">
                <Checkbox
                  checked={selectedIds.has(u.id)}
                  onChange={e =>
                    commit(
                      toggleSelection(
                        selected,
                        toSelection(u),
                        e.target.checked,
                      ),
                    )
                  }
                />
                <div>
                  <div>{(u.displayName || '').trim() || u.id}</div>
                  <ResultMeta>{describeSearchResult(u)}</ResultMeta>
                </div>
              </ResultRow>
            ))}
        </TreeBox>
      )}
      <TreeBox hidden={isSearchMode}>
        {loading && t('Loading…')}
        {error && <ErrorText>{error}</ErrorText>}
        {!loading && !error && treeData.length === 0 && (
          <div style={{ padding: 8, opacity: 0.7 }}>
            {cbmpTypes.length
              ? t('No org units match the selected CBMP type')
              : t('No org units found')}
          </div>
        )}
        {!loading && !error && treeData.length > 0 && (
          <Tree
            treeData={treeData}
            loadData={loadChildren as any}
            // Controlled expansion so a lazy-load (which patches new node
            // object references) doesn't auto-collapse an expanded node.
            expandedKeys={expandedKeys}
            onExpand={handleExpand}
            // Checkbox-based multi-select; checkStrictly so parent/child are
            // independent (checking a region does NOT auto-check its zones).
            checkable
            checkStrictly
            checkedKeys={{ checked: checkedKeys, halfChecked: [] }}
            onCheck={onCheck as any}
            blockNode
            showLine
          />
        )}
      </TreeBox>
    </Wrapper>
  );
}
