/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.
 */
import { t } from '@apache-superset/core/translation';
import { Behavior, ChartMetadata, ChartPlugin } from '@superset-ui/core';
import controlPanel from './controlPanel';
import transformProps from './transformProps';
// Reuse the Select filter's thumbnail until we ship a dedicated tree icon
// — avoids an unnecessary PNG asset in the bundle for now.
import thumbnail from '../Select/images/thumbnail.png';

export default class OrgUnitTreeFilterPlugin extends ChartPlugin {
  constructor() {
    const metadata = new ChartMetadata({
      name: t('Org Unit Tree'),
      description: t(
        'MoH hierarchical org unit picker — drill from country → region → zone → woreda → PHCU → health post. Selection populates region/zone/woreda/phcu/health_post filter dimensions automatically based on the chosen level.',
      ),
      behaviors: [Behavior.InteractiveChart, Behavior.NativeFilter],
      enableNoResults: false,
      tags: [t('MoH'), t('Experimental')],
      thumbnail,
      // Tree data comes from /api/v1/moh/dhis2 — no dataset query needed.
      // Match the Time filter pattern: datasourceCount=0 + no buildQuery.
      datasourceCount: 0,
    });

    super({
      controlPanel,
      loadChart: () => import('./OrgUnitTreeFilter'),
      metadata,
      transformProps,
    });
  }
}
