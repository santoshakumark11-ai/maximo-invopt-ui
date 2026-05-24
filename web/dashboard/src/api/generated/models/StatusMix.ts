/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type StatusMix = {
  total: number;
  segments: Array<{
    status: 'NEW' | 'PENDING' | 'APPROVED' | 'APPLIED' | 'REJECTED';
    count: number;
    pct: number;
  }>;
};
