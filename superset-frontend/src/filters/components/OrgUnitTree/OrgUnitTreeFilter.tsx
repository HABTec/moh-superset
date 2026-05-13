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
 * Datasets are untouched — they continue to read filter_values('region') etc.
 */
import { t } from '@apache-superset/core/translation';
import { styled } from '@apache-superset/core/theme';
import {
  Button,
  Tree,
  type TreeDataNode,
} from '@superset-ui/core/components';
import { useCallback, useEffect, useMemo, useState } from 'react';

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

const Wrapper = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 8px;
`;

const Header = styled.div`
  font-size: 12px;
  color: ${({ theme }) => theme.colorTextSecondary};
  padding: 0 4px;
`;

const TreeBox = styled.div`
  flex: 1;
  min-height: 240px;
  overflow: auto;
  border: 1px solid ${({ theme }) => theme.colorBorder};
  border-radius: 6px;
  padding: 6px 4px;
  background: ${({ theme }) => theme.colorBgContainer};
`;

const Actions = styled.div`
  display: flex;
  gap: 8px;
  justify-content: flex-end;
`;

const Selected = styled.div`
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  background: ${({ theme }) => theme.colorPrimaryBg};
  color: ${({ theme }) => theme.colorPrimaryText};
`;

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

export default function OrgUnitTreeFilter({
  formData,
  filterState,
  setDataMask,
}: OrgUnitTreeFilterProps) {
  const apiBaseUrl = formData.apiBaseUrl || '/api/v1/moh/dhis2';
  const rootLevel = Number(formData.rootLevel || 2);   // 2 = Region (matches MOH_ORG_UNITS_ROOT_LEVEL)
  const maxLevel = Number(formData.maxLevel || 6);

  const [treeData, setTreeData] = useState<Node[]>([]);
  // Multi-select: pending/applied are arrays of selections. Rich objects
  // (with id + level) live only in local state — what we send to Superset
  // is a simple string array per dimension so the filter chip displays
  // cleanly and dataset SQL gets the right WHERE clauses.
  const [pending, setPending] = useState<OrgUnitSelection[]>([]);
  const [applied, setApplied] = useState<OrgUnitSelection[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // -- initial root fetch ---------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(
          `${apiBaseUrl}/organisationUnits?level=${rootLevel}`,
          { credentials: 'same-origin' },
        );
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        if (cancelled) return;
        setTreeData(
          (data.organisationUnits || []).map((u: OrgUnit) =>
            toNode(u, maxLevel),
          ),
        );
        setError(null);
      } catch (e: any) {
        if (!cancelled) setError(e.message || 'Failed to load org units');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, rootLevel, maxLevel]);

  // -- lazy load on expand --------------------------------------------------
  const loadChildren = useCallback(
    async (node: Node): Promise<void> => {
      if (node.children && node.children.length > 0) return;
      try {
        const r = await fetch(
          `${apiBaseUrl}/organisationUnits/${node.unit.id}`,
          { credentials: 'same-origin' },
        );
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
    [apiBaseUrl, maxLevel],
  );

  // -- handlers -------------------------------------------------------------
  // AntD Tree's onCheck gives us the full node objects when checkStrictly is on,
  // which is what we need to extract level + displayName per selection.
  const onCheck = (_: any, info: { checkedNodes: Node[] }) => {
    const sels: OrgUnitSelection[] = info.checkedNodes
      .filter(n => n.unit)
      .map(n => ({
        id: n.unit.id,
        displayName: n.unit.displayName.trim(),
        level: n.unit.level,
      }));
    setPending(sels);
  };

  const dirty = useMemo(
    () => JSON.stringify(pending) !== JSON.stringify(applied),
    [pending, applied],
  );

  const apply = () => {
    setDataMask(buildDataMask(pending));
    setApplied(pending);
  };

  const clear = () => {
    setPending([]);
    setApplied([]);
    setDataMask(buildDataMask([]));
  };

  const checkedKeys = useMemo(() => pending.map(p => p.id), [pending]);

  return (
    <Wrapper>
      <Header>{t('Org unit')}</Header>
      {pending.length > 0 && (
        <Selected>
          {pending.length === 1
            ? `${pending[0].displayName} · L${pending[0].level}`
            : `${pending.length} selected: ${pending
                .map(s => s.displayName)
                .join(', ')}`}
        </Selected>
      )}
      <TreeBox>
        {loading && t('Loading…')}
        {error && <div style={{ color: 'red' }}>{error}</div>}
        {!loading && !error && (
          <Tree
            treeData={treeData}
            loadData={loadChildren as any}
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
      <Actions>
        <Button
          size="small"
          onClick={clear}
          disabled={applied.length === 0 && pending.length === 0}
        >
          {t('Clear')}
        </Button>
        <Button
          size="small"
          type="primary"
          onClick={apply}
          disabled={!dirty}
        >
          {t('Apply')}
        </Button>
      </Actions>
    </Wrapper>
  );
}

// ----------------------------------------------------------------------------

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
