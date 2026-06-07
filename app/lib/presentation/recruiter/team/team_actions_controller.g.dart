// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'team_actions_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Owner-only mutations on an employer's team. Each method runs through
/// `AsyncValue.guard` and invalidates the affected employer's roster + invites
/// controllers so the lists refetch (no in-place list mutation — mirrors the
/// applicant-side convention).

@ProviderFor(TeamActionsController)
final teamActionsControllerProvider = TeamActionsControllerProvider._();

/// Owner-only mutations on an employer's team. Each method runs through
/// `AsyncValue.guard` and invalidates the affected employer's roster + invites
/// controllers so the lists refetch (no in-place list mutation — mirrors the
/// applicant-side convention).
final class TeamActionsControllerProvider
    extends $AsyncNotifierProvider<TeamActionsController, void> {
  /// Owner-only mutations on an employer's team. Each method runs through
  /// `AsyncValue.guard` and invalidates the affected employer's roster + invites
  /// controllers so the lists refetch (no in-place list mutation — mirrors the
  /// applicant-side convention).
  TeamActionsControllerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'teamActionsControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$teamActionsControllerHash();

  @$internal
  @override
  TeamActionsController create() => TeamActionsController();
}

String _$teamActionsControllerHash() =>
    r'09472085675c72678d0a20d89ac15fde8c62bc65';

/// Owner-only mutations on an employer's team. Each method runs through
/// `AsyncValue.guard` and invalidates the affected employer's roster + invites
/// controllers so the lists refetch (no in-place list mutation — mirrors the
/// applicant-side convention).

abstract class _$TeamActionsController extends $AsyncNotifier<void> {
  FutureOr<void> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<AsyncValue<void>, void>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<AsyncValue<void>, void>,
        AsyncValue<void>,
        Object?,
        Object?>;
    element.handleCreate(ref, build);
  }
}
