import 'package:json_annotation/json_annotation.dart';

/// Mirrors the backend ResumeParseStatus StrEnum.
/// `unknown` is the forward-compat sentinel for an unrecognised wire value.
enum ResumeParseStatus {
  @JsonValue('pending')
  pending,
  @JsonValue('parsing')
  parsing,
  @JsonValue('parsed')
  parsed,
  @JsonValue('failed')
  failed,
  unknown,
}
