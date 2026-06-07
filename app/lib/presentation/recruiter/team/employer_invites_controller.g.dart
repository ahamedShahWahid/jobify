// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'employer_invites_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Pending invites for one employer. Family keyed by employerId.

@ProviderFor(employerInvitesController)
final employerInvitesControllerProvider = EmployerInvitesControllerFamily._();

/// Pending invites for one employer. Family keyed by employerId.

final class EmployerInvitesControllerProvider extends $FunctionalProvider<
        AsyncValue<List<InviteDto>>, List<InviteDto>, FutureOr<List<InviteDto>>>
    with $FutureModifier<List<InviteDto>>, $FutureProvider<List<InviteDto>> {
  /// Pending invites for one employer. Family keyed by employerId.
  EmployerInvitesControllerProvider._(
      {required EmployerInvitesControllerFamily super.from,
      required String super.argument})
      : super(
          retry: null,
          name: r'employerInvitesControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$employerInvitesControllerHash();

  @override
  String toString() {
    return r'employerInvitesControllerProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  $FutureProviderElement<List<InviteDto>> $createElement(
          $ProviderPointer pointer) =>
      $FutureProviderElement(pointer);

  @override
  FutureOr<List<InviteDto>> create(Ref ref) {
    final argument = this.argument as String;
    return employerInvitesController(
      ref,
      argument,
    );
  }

  @override
  bool operator ==(Object other) {
    return other is EmployerInvitesControllerProvider &&
        other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$employerInvitesControllerHash() =>
    r'0761af74e61757a96c98307636ece1dbcbfbed42';

/// Pending invites for one employer. Family keyed by employerId.

final class EmployerInvitesControllerFamily extends $Family
    with $FunctionalFamilyOverride<FutureOr<List<InviteDto>>, String> {
  EmployerInvitesControllerFamily._()
      : super(
          retry: null,
          name: r'employerInvitesControllerProvider',
          dependencies: null,
          $allTransitiveDependencies: null,
          isAutoDispose: true,
        );

  /// Pending invites for one employer. Family keyed by employerId.

  EmployerInvitesControllerProvider call(
    String employerId,
  ) =>
      EmployerInvitesControllerProvider._(argument: employerId, from: this);

  @override
  String toString() => r'employerInvitesControllerProvider';
}
