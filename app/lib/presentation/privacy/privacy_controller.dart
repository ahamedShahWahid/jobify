import 'package:flutter/services.dart';
import 'package:jobify_app/data/consents/consent_dto.dart';
import 'package:jobify_app/data/consents/consents_repository_impl.dart';
import 'package:jobify_app/data/dsr/dsr_repository_impl.dart';
import 'package:jobify_app/presentation/privacy/privacy_state.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'privacy_controller.g.dart';

@Riverpod(keepAlive: true)
class PrivacyController extends _$PrivacyController {
  @override
  Future<PrivacyState> build() async {
    final list = await ref.read(consentsRepositoryProvider).list();
    return PrivacyState(consents: list.items);
  }

  Future<void> setConsent(String scope, {required bool granted}) async {
    final current = state.value;
    if (current == null) return;

    final repo = ref.read(consentsRepositoryProvider);

    // Capture pre-mutation list for potential rollback.
    final previous = current.consents;

    // Optimistic update.
    final optimistic = [
      for (final c in current.consents)
        if (c.scope == scope)
          ConsentDto(scope: c.scope, granted: granted, updatedAt: c.updatedAt)
        else
          c,
    ];
    state =
        AsyncData(current.copyWith(consents: optimistic, mutationError: null));

    try {
      final updated = await repo.patch(scope, granted: granted);
      // Replace optimistic item with canonical server response.
      final canonical = [
        for (final c in current.consents)
          if (c.scope == scope) updated else c,
      ];
      state = AsyncData(current.copyWith(consents: canonical));
    } catch (e) {
      // Rollback on error.
      state = AsyncData(
        current.copyWith(
          consents: previous,
          mutationError: e,
        ),
      );
    }
  }

  /// Calls POST /v1/me/dsr/export and copies the envelope to the clipboard.
  /// Returns the envelope string on success, null on failure.
  Future<String?> exportData() async {
    final current = state.value;
    if (current == null) return null;
    state = AsyncData(
      current.copyWith(exportInProgress: true, mutationError: null),
    );
    try {
      final envelope = await ref.read(dsrRepositoryProvider).exportData();
      await Clipboard.setData(ClipboardData(text: envelope));
      state = AsyncData(current.copyWith(exportInProgress: false));
      return envelope;
    } catch (e) {
      state = AsyncData(
        current.copyWith(
          exportInProgress: false,
          mutationError: e,
        ),
      );
      return null;
    }
  }
}
