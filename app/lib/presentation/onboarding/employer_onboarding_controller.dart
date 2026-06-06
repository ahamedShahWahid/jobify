import 'package:kpa_app/data/auth/auth_repository_provider.dart';
import 'package:kpa_app/data/employers/employer_dto.dart';
import 'package:kpa_app/data/employers/employer_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'employer_onboarding_controller.g.dart';

@riverpod
class EmployerOnboardingController extends _$EmployerOnboardingController {
  @override
  FutureOr<EmployerDto?> build() => null;

  /// Create the employer and flip the session role to recruiter.
  Future<void> submit({required String name, String? gst}) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final repo = ref.read(employerRepositoryProvider);
      final employer = await repo.createEmployer(name: name, gst: gst);
      await ref.read(authRepositoryProvider).refreshSession();
      return employer;
    });
  }
}
