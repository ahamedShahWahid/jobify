// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'members_controller.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// The roster for one employer. Family keyed by employerId.

@ProviderFor(membersController)
final membersControllerProvider = MembersControllerFamily._();

/// The roster for one employer. Family keyed by employerId.

final class MembersControllerProvider extends $FunctionalProvider<
        AsyncValue<List<MemberDto>>, List<MemberDto>, FutureOr<List<MemberDto>>>
    with $FutureModifier<List<MemberDto>>, $FutureProvider<List<MemberDto>> {
  /// The roster for one employer. Family keyed by employerId.
  MembersControllerProvider._(
      {required MembersControllerFamily super.from,
      required String super.argument})
      : super(
          retry: null,
          name: r'membersControllerProvider',
          isAutoDispose: true,
          dependencies: null,
          $allTransitiveDependencies: null,
        );

  @override
  String debugGetCreateSourceHash() => _$membersControllerHash();

  @override
  String toString() {
    return r'membersControllerProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  $FutureProviderElement<List<MemberDto>> $createElement(
          $ProviderPointer pointer) =>
      $FutureProviderElement(pointer);

  @override
  FutureOr<List<MemberDto>> create(Ref ref) {
    final argument = this.argument as String;
    return membersController(
      ref,
      argument,
    );
  }

  @override
  bool operator ==(Object other) {
    return other is MembersControllerProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$membersControllerHash() => r'3ce53453062c1d03b4ddb1c5ae72df41683071ae';

/// The roster for one employer. Family keyed by employerId.

final class MembersControllerFamily extends $Family
    with $FunctionalFamilyOverride<FutureOr<List<MemberDto>>, String> {
  MembersControllerFamily._()
      : super(
          retry: null,
          name: r'membersControllerProvider',
          dependencies: null,
          $allTransitiveDependencies: null,
          isAutoDispose: true,
        );

  /// The roster for one employer. Family keyed by employerId.

  MembersControllerProvider call(
    String employerId,
  ) =>
      MembersControllerProvider._(argument: employerId, from: this);

  @override
  String toString() => r'membersControllerProvider';
}
