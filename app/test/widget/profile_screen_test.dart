import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/me/me_dto.dart';
import 'package:kpa_app/data/me/me_repository_impl.dart';
import 'package:kpa_app/domain/me/me_repository.dart';
import 'package:kpa_app/presentation/profile/profile_screen.dart';

class _FakeRepo implements MeRepository {
  _FakeRepo(this.me);
  final MeDto me;
  @override
  Future<MeDto> fetch() async => me;
}

void main() {
  testWidgets(
    'renders user name + email + Coming soon rows + Sign out',
    (tester) async {
      final me = MeDto(
        user: MeUserDto(
          id: 'u1',
          email: 'eng@example.com',
          displayName: 'Eng U',
          role: 'applicant',
          createdAt: DateTime(2026, 1, 1),
        ),
        applicant: const ApplicantSummaryDto(id: 'a1', userId: 'u1'),
      );
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            meRepositoryProvider.overrideWithValue(_FakeRepo(me)),
          ],
          child: MaterialApp(
            theme: ThemeData.light(useMaterial3: true),
            home: const ProfileScreen(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Eng U'), findsOneWidget);
      expect(find.text('eng@example.com'), findsOneWidget);
      expect(find.text('Resume'), findsOneWidget);
      expect(find.text('Notifications'), findsOneWidget);
      expect(find.text('Sign out'), findsOneWidget);
    },
  );
}
