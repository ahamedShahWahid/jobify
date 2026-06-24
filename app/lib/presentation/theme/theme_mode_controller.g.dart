// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'theme_mode_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Persisted theme-mode preference. Defaults to [ThemeMode.system].
///
/// Stored as a string under [_kThemeModeKey] in [SharedPreferences].

@ProviderFor(ThemeModeController)
final themeModeControllerProvider = ThemeModeControllerProvider._();

/// Persisted theme-mode preference. Defaults to [ThemeMode.system].
///
/// Stored as a string under [_kThemeModeKey] in [SharedPreferences].
final class ThemeModeControllerProvider
    extends $NotifierProvider<ThemeModeController, ThemeMode> {
  /// Persisted theme-mode preference. Defaults to [ThemeMode.system].
  ///
  /// Stored as a string under [_kThemeModeKey] in [SharedPreferences].
  ThemeModeControllerProvider._()
      : super(
          from: null,
          argument: null,
          retry: null,
          name: r'themeModeControllerProvider',
          isAutoDispose: false,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$themeModeControllerHash();

  @$internal
  @override
  ThemeModeController create() => ThemeModeController();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(ThemeMode value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<ThemeMode>(value),
    );
  }
}

String _$themeModeControllerHash() =>
    r'efdd4dcdaedc034f7f379900ea22d984b6ee9df8';

/// Persisted theme-mode preference. Defaults to [ThemeMode.system].
///
/// Stored as a string under [_kThemeModeKey] in [SharedPreferences].

abstract class _$ThemeModeController extends $Notifier<ThemeMode> {
  ThemeMode build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<ThemeMode, ThemeMode>;
    final element = ref.element as $ClassProviderElement<
        AnyNotifier<ThemeMode, ThemeMode>, ThemeMode, Object?, Object?>;
    element.handleCreate(ref, build);
  }
}
