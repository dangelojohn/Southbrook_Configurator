{{/* Common labels and naming helpers. */}}

{{- define "kitchenforge.name" -}}
{{- default .Chart.Name .Values.tenant.slug | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "kitchenforge.fullname" -}}
{{- printf "%s-%s" (include "kitchenforge.name" .) .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "kitchenforge.labels" -}}
app.kubernetes.io/name: {{ include "kitchenforge.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
kitchenforge.io/tenant: {{ .Values.tenant.slug | quote }}
kitchenforge.io/tier: {{ .Values.tenant.tier | quote }}
{{- end -}}
