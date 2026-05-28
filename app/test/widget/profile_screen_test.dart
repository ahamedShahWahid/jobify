import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/me/me_dto.dart';
import 'package:kpa_app/data/me/me_repository.dart';
import 'package:kpa_app/data/me/me_repository_impl.dart';
import 'package:kpa_app/data/me/profile_update_dto.dart';
import 'package:kpa_app/presentation/profile/profile_screen.dart';

class _FakeRepo implements MeRepository {
  _FakeRepo(this.me);
  final MeDto me;
  @override
  Future<MeDto> fetch() async => me;
  @override
  Future<MeDto> updateProfile(ProfileUpdateDto update) async => me;
}

void main() {
  testWidgets(
    'renders user name + email + résumé/notifications rows + Sign out',
    (tester) async {
      const me = MeDto(
        id: 'u1',
        email: 'eng@example.com',
        displayName: 'Eng U',
        role: 'applicant',
        applicant: ApplicantSummaryDto(
          id: 'a1',
          fullName: 'Eng U',
          locations: ['Pune'],
          expectedCtc: '1800000.00',
        ),
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
      expect(find.text('Résumé'), findsOneWidget);
      expect(find.text('Notifications'), findsOneWidget);
      expect(find.text('Sign out'), findsOneWidget);
      expect(find.text('Locations'), findsOneWidget);
      expect(find.text('Pune'), findsOneWidget);
      expect(find.text('Edit'), findsOneWidget);
    },
  );
}
