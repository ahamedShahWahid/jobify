import 'package:freezed_annotation/freezed_annotation.dart';

import 'package:jobify_app/data/consents/consent_dto.dart';

part 'privacy_state.freezed.dart';

@freezed
abstract class PrivacyState with _$PrivacyState {
  const factory PrivacyState({
    required List<ConsentDto> consents,
    @Default(false) bool exportInProgress,
    Object? mutationError,
  }) = _PrivacyState;
}
