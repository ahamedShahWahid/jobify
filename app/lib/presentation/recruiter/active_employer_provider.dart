import 'package:kpa_app/data/employers/employer_dto.dart';
import 'package:kpa_app/data/employers/employer_repository_impl.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'active_employer_provider.g.dart';

@Riverpod(keepAlive: true)
Future<List<EmployerDto>> recruiterEmployers(Ref ref) =>
    ref.read(employerRepositoryProvider).listMyEmployers();

@Riverpod(keepAlive: true)
class ActiveEmployer extends _$ActiveEmployer {
  @override
  EmployerDto? build() => null;

  // ignore: use_setters_to_change_properties
  void select(EmployerDto e) => state = e;
}
