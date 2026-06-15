// SPDX-License-Identifier: LGPL-3.0-only
// Public exports for @kitchenforge/sdk.

export {
  KitchenForgeClient,
  KitchenForgeError,
  ApiError,
  NotFoundError,
  PreconditionFailedError,
} from "./client.js";

export type {
  AddZoneRequest,
  AddZoneResult,
  AgentManifest,
  ConfirmQuoteRequest,
  ConfirmQuoteResult,
  ErrorEnvelope,
  FsDirListing,
  FsEntry,
  FsFile,
  FsResult,
  InstantiateRequest,
  InstantiateResult,
  KitchenForgeClientOptions,
  MarathonTelemetry,
  RaiseEcoRequest,
  RaiseEcoResult,
  RebateSummary,
  ReleaseMosRequest,
  ReleaseMosResult,
  RequestOptions,
  RoomDims,
  SpecEvent,
  ToolCatalog,
  ToolDescriptor,
  Zone,
} from "./types.js";

export {
  SCHEMA_API,
  SCHEMA_FS,
  SCHEMA_TOOLS,
} from "./types.js";
