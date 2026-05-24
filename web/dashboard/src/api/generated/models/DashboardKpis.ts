/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DashboardKpis = {
  workingCapital: {
    released: number;
    deltaVsPrior: number;
    ytd: number;
  };
  openRecommendations: {
    total: number;
    pendingApproval: number;
    avgApprovalDays: number;
  };
  forecastAccuracy: {
    wape: number;
    deltaPctPts: number;
    coverage: string;
  };
  stockOutRisks: {
    active: number;
    safetyCritical: number;
    autoUpliftApplied: number;
  };
  asOf: string;
};
