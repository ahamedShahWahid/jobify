// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'jobs_dto.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$JobDetailDto {
  JobSummaryDto get job;
  EmployerSummaryDto get employer;
  MatchSummaryDto? get match;
  ApplicationDto? get application;
  SavedJobDto? get savedJob;

  /// Create a copy of JobDetailDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $JobDetailDtoCopyWith<JobDetailDto> get copyWith =>
      _$JobDetailDtoCopyWithImpl<JobDetailDto>(
          this as JobDetailDto, _$identity);

  /// Serializes this JobDetailDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is JobDetailDto &&
            (identical(other.job, job) || other.job == job) &&
            (identical(other.employer, employer) ||
                other.employer == employer) &&
            (identical(other.match, match) || other.match == match) &&
            (identical(other.application, application) ||
                other.application == application) &&
            (identical(other.savedJob, savedJob) ||
                other.savedJob == savedJob));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode =>
      Object.hash(runtimeType, job, employer, match, application, savedJob);

  @override
  String toString() {
    return 'JobDetailDto(job: $job, employer: $employer, match: $match, application: $application, savedJob: $savedJob)';
  }
}

/// @nodoc
abstract mixin class $JobDetailDtoCopyWith<$Res> {
  factory $JobDetailDtoCopyWith(
          JobDetailDto value, $Res Function(JobDetailDto) _then) =
      _$JobDetailDtoCopyWithImpl;
  @useResult
  $Res call(
      {JobSummaryDto job,
      EmployerSummaryDto employer,
      MatchSummaryDto? match,
      ApplicationDto? application,
      SavedJobDto? savedJob});

  $JobSummaryDtoCopyWith<$Res> get job;
  $EmployerSummaryDtoCopyWith<$Res> get employer;
  $MatchSummaryDtoCopyWith<$Res>? get match;
  $ApplicationDtoCopyWith<$Res>? get application;
  $SavedJobDtoCopyWith<$Res>? get savedJob;
}

/// @nodoc
class _$JobDetailDtoCopyWithImpl<$Res> implements $JobDetailDtoCopyWith<$Res> {
  _$JobDetailDtoCopyWithImpl(this._self, this._then);

  final JobDetailDto _self;
  final $Res Function(JobDetailDto) _then;

  /// Create a copy of JobDetailDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? job = null,
    Object? employer = null,
    Object? match = freezed,
    Object? application = freezed,
    Object? savedJob = freezed,
  }) {
    return _then(_self.copyWith(
      job: null == job
          ? _self.job
          : job // ignore: cast_nullable_to_non_nullable
              as JobSummaryDto,
      employer: null == employer
          ? _self.employer
          : employer // ignore: cast_nullable_to_non_nullable
              as EmployerSummaryDto,
      match: freezed == match
          ? _self.match
          : match // ignore: cast_nullable_to_non_nullable
              as MatchSummaryDto?,
      application: freezed == application
          ? _self.application
          : application // ignore: cast_nullable_to_non_nullable
              as ApplicationDto?,
      savedJob: freezed == savedJob
          ? _self.savedJob
          : savedJob // ignore: cast_nullable_to_non_nullable
              as SavedJobDto?,
    ));
  }

  /// Create a copy of JobDetailDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $JobSummaryDtoCopyWith<$Res> get job {
    return $JobSummaryDtoCopyWith<$Res>(_self.job, (value) {
      return _then(_self.copyWith(job: value));
    });
  }

  /// Create a copy of JobDetailDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $EmployerSummaryDtoCopyWith<$Res> get employer {
    return $EmployerSummaryDtoCopyWith<$Res>(_self.employer, (value) {
      return _then(_self.copyWith(employer: value));
    });
  }

  /// Create a copy of JobDetailDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $MatchSummaryDtoCopyWith<$Res>? get match {
    if (_self.match == null) {
      return null;
    }

    return $MatchSummaryDtoCopyWith<$Res>(_self.match!, (value) {
      return _then(_self.copyWith(match: value));
    });
  }

  /// Create a copy of JobDetailDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $ApplicationDtoCopyWith<$Res>? get application {
    if (_self.application == null) {
      return null;
    }

    return $ApplicationDtoCopyWith<$Res>(_self.application!, (value) {
      return _then(_self.copyWith(application: value));
    });
  }

  /// Create a copy of JobDetailDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $SavedJobDtoCopyWith<$Res>? get savedJob {
    if (_self.savedJob == null) {
      return null;
    }

    return $SavedJobDtoCopyWith<$Res>(_self.savedJob!, (value) {
      return _then(_self.copyWith(savedJob: value));
    });
  }
}

/// Adds pattern-matching-related methods to [JobDetailDto].
extension JobDetailDtoPatterns on JobDetailDto {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_JobDetailDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _JobDetailDto() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_JobDetailDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _JobDetailDto():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_JobDetailDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _JobDetailDto() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(
            JobSummaryDto job,
            EmployerSummaryDto employer,
            MatchSummaryDto? match,
            ApplicationDto? application,
            SavedJobDto? savedJob)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _JobDetailDto() when $default != null:
        return $default(_that.job, _that.employer, _that.match,
            _that.application, _that.savedJob);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(
            JobSummaryDto job,
            EmployerSummaryDto employer,
            MatchSummaryDto? match,
            ApplicationDto? application,
            SavedJobDto? savedJob)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _JobDetailDto():
        return $default(_that.job, _that.employer, _that.match,
            _that.application, _that.savedJob);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(
            JobSummaryDto job,
            EmployerSummaryDto employer,
            MatchSummaryDto? match,
            ApplicationDto? application,
            SavedJobDto? savedJob)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _JobDetailDto() when $default != null:
        return $default(_that.job, _that.employer, _that.match,
            _that.application, _that.savedJob);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _JobDetailDto implements JobDetailDto {
  const _JobDetailDto(
      {required this.job,
      required this.employer,
      this.match,
      this.application,
      this.savedJob});
  factory _JobDetailDto.fromJson(Map<String, dynamic> json) =>
      _$JobDetailDtoFromJson(json);

  @override
  final JobSummaryDto job;
  @override
  final EmployerSummaryDto employer;
  @override
  final MatchSummaryDto? match;
  @override
  final ApplicationDto? application;
  @override
  final SavedJobDto? savedJob;

  /// Create a copy of JobDetailDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$JobDetailDtoCopyWith<_JobDetailDto> get copyWith =>
      __$JobDetailDtoCopyWithImpl<_JobDetailDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$JobDetailDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _JobDetailDto &&
            (identical(other.job, job) || other.job == job) &&
            (identical(other.employer, employer) ||
                other.employer == employer) &&
            (identical(other.match, match) || other.match == match) &&
            (identical(other.application, application) ||
                other.application == application) &&
            (identical(other.savedJob, savedJob) ||
                other.savedJob == savedJob));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode =>
      Object.hash(runtimeType, job, employer, match, application, savedJob);

  @override
  String toString() {
    return 'JobDetailDto(job: $job, employer: $employer, match: $match, application: $application, savedJob: $savedJob)';
  }
}

/// @nodoc
abstract mixin class _$JobDetailDtoCopyWith<$Res>
    implements $JobDetailDtoCopyWith<$Res> {
  factory _$JobDetailDtoCopyWith(
          _JobDetailDto value, $Res Function(_JobDetailDto) _then) =
      __$JobDetailDtoCopyWithImpl;
  @override
  @useResult
  $Res call(
      {JobSummaryDto job,
      EmployerSummaryDto employer,
      MatchSummaryDto? match,
      ApplicationDto? application,
      SavedJobDto? savedJob});

  @override
  $JobSummaryDtoCopyWith<$Res> get job;
  @override
  $EmployerSummaryDtoCopyWith<$Res> get employer;
  @override
  $MatchSummaryDtoCopyWith<$Res>? get match;
  @override
  $ApplicationDtoCopyWith<$Res>? get application;
  @override
  $SavedJobDtoCopyWith<$Res>? get savedJob;
}

/// @nodoc
class __$JobDetailDtoCopyWithImpl<$Res>
    implements _$JobDetailDtoCopyWith<$Res> {
  __$JobDetailDtoCopyWithImpl(this._self, this._then);

  final _JobDetailDto _self;
  final $Res Function(_JobDetailDto) _then;

  /// Create a copy of JobDetailDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? job = null,
    Object? employer = null,
    Object? match = freezed,
    Object? application = freezed,
    Object? savedJob = freezed,
  }) {
    return _then(_JobDetailDto(
      job: null == job
          ? _self.job
          : job // ignore: cast_nullable_to_non_nullable
              as JobSummaryDto,
      employer: null == employer
          ? _self.employer
          : employer // ignore: cast_nullable_to_non_nullable
              as EmployerSummaryDto,
      match: freezed == match
          ? _self.match
          : match // ignore: cast_nullable_to_non_nullable
              as MatchSummaryDto?,
      application: freezed == application
          ? _self.application
          : application // ignore: cast_nullable_to_non_nullable
              as ApplicationDto?,
      savedJob: freezed == savedJob
          ? _self.savedJob
          : savedJob // ignore: cast_nullable_to_non_nullable
              as SavedJobDto?,
    ));
  }

  /// Create a copy of JobDetailDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $JobSummaryDtoCopyWith<$Res> get job {
    return $JobSummaryDtoCopyWith<$Res>(_self.job, (value) {
      return _then(_self.copyWith(job: value));
    });
  }

  /// Create a copy of JobDetailDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $EmployerSummaryDtoCopyWith<$Res> get employer {
    return $EmployerSummaryDtoCopyWith<$Res>(_self.employer, (value) {
      return _then(_self.copyWith(employer: value));
    });
  }

  /// Create a copy of JobDetailDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $MatchSummaryDtoCopyWith<$Res>? get match {
    if (_self.match == null) {
      return null;
    }

    return $MatchSummaryDtoCopyWith<$Res>(_self.match!, (value) {
      return _then(_self.copyWith(match: value));
    });
  }

  /// Create a copy of JobDetailDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $ApplicationDtoCopyWith<$Res>? get application {
    if (_self.application == null) {
      return null;
    }

    return $ApplicationDtoCopyWith<$Res>(_self.application!, (value) {
      return _then(_self.copyWith(application: value));
    });
  }

  /// Create a copy of JobDetailDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $SavedJobDtoCopyWith<$Res>? get savedJob {
    if (_self.savedJob == null) {
      return null;
    }

    return $SavedJobDtoCopyWith<$Res>(_self.savedJob!, (value) {
      return _then(_self.copyWith(savedJob: value));
    });
  }
}

/// @nodoc
mixin _$ApplicationDto {
  String get id;
  String get applicantId;
  String get jobId;
  String get status;
  String get source;
  DateTime get createdAt;
  DateTime? get withdrawnAt;

  /// Create a copy of ApplicationDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $ApplicationDtoCopyWith<ApplicationDto> get copyWith =>
      _$ApplicationDtoCopyWithImpl<ApplicationDto>(
          this as ApplicationDto, _$identity);

  /// Serializes this ApplicationDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is ApplicationDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.applicantId, applicantId) ||
                other.applicantId == applicantId) &&
            (identical(other.jobId, jobId) || other.jobId == jobId) &&
            (identical(other.status, status) || other.status == status) &&
            (identical(other.source, source) || other.source == source) &&
            (identical(other.createdAt, createdAt) ||
                other.createdAt == createdAt) &&
            (identical(other.withdrawnAt, withdrawnAt) ||
                other.withdrawnAt == withdrawnAt));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, id, applicantId, jobId, status,
      source, createdAt, withdrawnAt);

  @override
  String toString() {
    return 'ApplicationDto(id: $id, applicantId: $applicantId, jobId: $jobId, status: $status, source: $source, createdAt: $createdAt, withdrawnAt: $withdrawnAt)';
  }
}

/// @nodoc
abstract mixin class $ApplicationDtoCopyWith<$Res> {
  factory $ApplicationDtoCopyWith(
          ApplicationDto value, $Res Function(ApplicationDto) _then) =
      _$ApplicationDtoCopyWithImpl;
  @useResult
  $Res call(
      {String id,
      String applicantId,
      String jobId,
      String status,
      String source,
      DateTime createdAt,
      DateTime? withdrawnAt});
}

/// @nodoc
class _$ApplicationDtoCopyWithImpl<$Res>
    implements $ApplicationDtoCopyWith<$Res> {
  _$ApplicationDtoCopyWithImpl(this._self, this._then);

  final ApplicationDto _self;
  final $Res Function(ApplicationDto) _then;

  /// Create a copy of ApplicationDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? id = null,
    Object? applicantId = null,
    Object? jobId = null,
    Object? status = null,
    Object? source = null,
    Object? createdAt = null,
    Object? withdrawnAt = freezed,
  }) {
    return _then(_self.copyWith(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      applicantId: null == applicantId
          ? _self.applicantId
          : applicantId // ignore: cast_nullable_to_non_nullable
              as String,
      jobId: null == jobId
          ? _self.jobId
          : jobId // ignore: cast_nullable_to_non_nullable
              as String,
      status: null == status
          ? _self.status
          : status // ignore: cast_nullable_to_non_nullable
              as String,
      source: null == source
          ? _self.source
          : source // ignore: cast_nullable_to_non_nullable
              as String,
      createdAt: null == createdAt
          ? _self.createdAt
          : createdAt // ignore: cast_nullable_to_non_nullable
              as DateTime,
      withdrawnAt: freezed == withdrawnAt
          ? _self.withdrawnAt
          : withdrawnAt // ignore: cast_nullable_to_non_nullable
              as DateTime?,
    ));
  }
}

/// Adds pattern-matching-related methods to [ApplicationDto].
extension ApplicationDtoPatterns on ApplicationDto {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_ApplicationDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _ApplicationDto() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_ApplicationDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicationDto():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_ApplicationDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicationDto() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(String id, String applicantId, String jobId, String status,
            String source, DateTime createdAt, DateTime? withdrawnAt)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _ApplicationDto() when $default != null:
        return $default(_that.id, _that.applicantId, _that.jobId, _that.status,
            _that.source, _that.createdAt, _that.withdrawnAt);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(String id, String applicantId, String jobId, String status,
            String source, DateTime createdAt, DateTime? withdrawnAt)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicationDto():
        return $default(_that.id, _that.applicantId, _that.jobId, _that.status,
            _that.source, _that.createdAt, _that.withdrawnAt);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(
            String id,
            String applicantId,
            String jobId,
            String status,
            String source,
            DateTime createdAt,
            DateTime? withdrawnAt)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicationDto() when $default != null:
        return $default(_that.id, _that.applicantId, _that.jobId, _that.status,
            _that.source, _that.createdAt, _that.withdrawnAt);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _ApplicationDto implements ApplicationDto {
  const _ApplicationDto(
      {required this.id,
      required this.applicantId,
      required this.jobId,
      required this.status,
      required this.source,
      required this.createdAt,
      this.withdrawnAt});
  factory _ApplicationDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicationDtoFromJson(json);

  @override
  final String id;
  @override
  final String applicantId;
  @override
  final String jobId;
  @override
  final String status;
  @override
  final String source;
  @override
  final DateTime createdAt;
  @override
  final DateTime? withdrawnAt;

  /// Create a copy of ApplicationDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$ApplicationDtoCopyWith<_ApplicationDto> get copyWith =>
      __$ApplicationDtoCopyWithImpl<_ApplicationDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$ApplicationDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _ApplicationDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.applicantId, applicantId) ||
                other.applicantId == applicantId) &&
            (identical(other.jobId, jobId) || other.jobId == jobId) &&
            (identical(other.status, status) || other.status == status) &&
            (identical(other.source, source) || other.source == source) &&
            (identical(other.createdAt, createdAt) ||
                other.createdAt == createdAt) &&
            (identical(other.withdrawnAt, withdrawnAt) ||
                other.withdrawnAt == withdrawnAt));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, id, applicantId, jobId, status,
      source, createdAt, withdrawnAt);

  @override
  String toString() {
    return 'ApplicationDto(id: $id, applicantId: $applicantId, jobId: $jobId, status: $status, source: $source, createdAt: $createdAt, withdrawnAt: $withdrawnAt)';
  }
}

/// @nodoc
abstract mixin class _$ApplicationDtoCopyWith<$Res>
    implements $ApplicationDtoCopyWith<$Res> {
  factory _$ApplicationDtoCopyWith(
          _ApplicationDto value, $Res Function(_ApplicationDto) _then) =
      __$ApplicationDtoCopyWithImpl;
  @override
  @useResult
  $Res call(
      {String id,
      String applicantId,
      String jobId,
      String status,
      String source,
      DateTime createdAt,
      DateTime? withdrawnAt});
}

/// @nodoc
class __$ApplicationDtoCopyWithImpl<$Res>
    implements _$ApplicationDtoCopyWith<$Res> {
  __$ApplicationDtoCopyWithImpl(this._self, this._then);

  final _ApplicationDto _self;
  final $Res Function(_ApplicationDto) _then;

  /// Create a copy of ApplicationDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? id = null,
    Object? applicantId = null,
    Object? jobId = null,
    Object? status = null,
    Object? source = null,
    Object? createdAt = null,
    Object? withdrawnAt = freezed,
  }) {
    return _then(_ApplicationDto(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      applicantId: null == applicantId
          ? _self.applicantId
          : applicantId // ignore: cast_nullable_to_non_nullable
              as String,
      jobId: null == jobId
          ? _self.jobId
          : jobId // ignore: cast_nullable_to_non_nullable
              as String,
      status: null == status
          ? _self.status
          : status // ignore: cast_nullable_to_non_nullable
              as String,
      source: null == source
          ? _self.source
          : source // ignore: cast_nullable_to_non_nullable
              as String,
      createdAt: null == createdAt
          ? _self.createdAt
          : createdAt // ignore: cast_nullable_to_non_nullable
              as DateTime,
      withdrawnAt: freezed == withdrawnAt
          ? _self.withdrawnAt
          : withdrawnAt // ignore: cast_nullable_to_non_nullable
              as DateTime?,
    ));
  }
}

/// @nodoc
mixin _$SavedJobDto {
  String get id;
  String get applicantId;
  String get jobId;
  DateTime get createdAt;

  /// Create a copy of SavedJobDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $SavedJobDtoCopyWith<SavedJobDto> get copyWith =>
      _$SavedJobDtoCopyWithImpl<SavedJobDto>(this as SavedJobDto, _$identity);

  /// Serializes this SavedJobDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is SavedJobDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.applicantId, applicantId) ||
                other.applicantId == applicantId) &&
            (identical(other.jobId, jobId) || other.jobId == jobId) &&
            (identical(other.createdAt, createdAt) ||
                other.createdAt == createdAt));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode =>
      Object.hash(runtimeType, id, applicantId, jobId, createdAt);

  @override
  String toString() {
    return 'SavedJobDto(id: $id, applicantId: $applicantId, jobId: $jobId, createdAt: $createdAt)';
  }
}

/// @nodoc
abstract mixin class $SavedJobDtoCopyWith<$Res> {
  factory $SavedJobDtoCopyWith(
          SavedJobDto value, $Res Function(SavedJobDto) _then) =
      _$SavedJobDtoCopyWithImpl;
  @useResult
  $Res call({String id, String applicantId, String jobId, DateTime createdAt});
}

/// @nodoc
class _$SavedJobDtoCopyWithImpl<$Res> implements $SavedJobDtoCopyWith<$Res> {
  _$SavedJobDtoCopyWithImpl(this._self, this._then);

  final SavedJobDto _self;
  final $Res Function(SavedJobDto) _then;

  /// Create a copy of SavedJobDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? id = null,
    Object? applicantId = null,
    Object? jobId = null,
    Object? createdAt = null,
  }) {
    return _then(_self.copyWith(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      applicantId: null == applicantId
          ? _self.applicantId
          : applicantId // ignore: cast_nullable_to_non_nullable
              as String,
      jobId: null == jobId
          ? _self.jobId
          : jobId // ignore: cast_nullable_to_non_nullable
              as String,
      createdAt: null == createdAt
          ? _self.createdAt
          : createdAt // ignore: cast_nullable_to_non_nullable
              as DateTime,
    ));
  }
}

/// Adds pattern-matching-related methods to [SavedJobDto].
extension SavedJobDtoPatterns on SavedJobDto {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_SavedJobDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _SavedJobDto() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_SavedJobDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedJobDto():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_SavedJobDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedJobDto() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(
            String id, String applicantId, String jobId, DateTime createdAt)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _SavedJobDto() when $default != null:
        return $default(
            _that.id, _that.applicantId, _that.jobId, _that.createdAt);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(
            String id, String applicantId, String jobId, DateTime createdAt)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedJobDto():
        return $default(
            _that.id, _that.applicantId, _that.jobId, _that.createdAt);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(
            String id, String applicantId, String jobId, DateTime createdAt)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedJobDto() when $default != null:
        return $default(
            _that.id, _that.applicantId, _that.jobId, _that.createdAt);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _SavedJobDto implements SavedJobDto {
  const _SavedJobDto(
      {required this.id,
      required this.applicantId,
      required this.jobId,
      required this.createdAt});
  factory _SavedJobDto.fromJson(Map<String, dynamic> json) =>
      _$SavedJobDtoFromJson(json);

  @override
  final String id;
  @override
  final String applicantId;
  @override
  final String jobId;
  @override
  final DateTime createdAt;

  /// Create a copy of SavedJobDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$SavedJobDtoCopyWith<_SavedJobDto> get copyWith =>
      __$SavedJobDtoCopyWithImpl<_SavedJobDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$SavedJobDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _SavedJobDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.applicantId, applicantId) ||
                other.applicantId == applicantId) &&
            (identical(other.jobId, jobId) || other.jobId == jobId) &&
            (identical(other.createdAt, createdAt) ||
                other.createdAt == createdAt));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode =>
      Object.hash(runtimeType, id, applicantId, jobId, createdAt);

  @override
  String toString() {
    return 'SavedJobDto(id: $id, applicantId: $applicantId, jobId: $jobId, createdAt: $createdAt)';
  }
}

/// @nodoc
abstract mixin class _$SavedJobDtoCopyWith<$Res>
    implements $SavedJobDtoCopyWith<$Res> {
  factory _$SavedJobDtoCopyWith(
          _SavedJobDto value, $Res Function(_SavedJobDto) _then) =
      __$SavedJobDtoCopyWithImpl;
  @override
  @useResult
  $Res call({String id, String applicantId, String jobId, DateTime createdAt});
}

/// @nodoc
class __$SavedJobDtoCopyWithImpl<$Res> implements _$SavedJobDtoCopyWith<$Res> {
  __$SavedJobDtoCopyWithImpl(this._self, this._then);

  final _SavedJobDto _self;
  final $Res Function(_SavedJobDto) _then;

  /// Create a copy of SavedJobDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? id = null,
    Object? applicantId = null,
    Object? jobId = null,
    Object? createdAt = null,
  }) {
    return _then(_SavedJobDto(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      applicantId: null == applicantId
          ? _self.applicantId
          : applicantId // ignore: cast_nullable_to_non_nullable
              as String,
      jobId: null == jobId
          ? _self.jobId
          : jobId // ignore: cast_nullable_to_non_nullable
              as String,
      createdAt: null == createdAt
          ? _self.createdAt
          : createdAt // ignore: cast_nullable_to_non_nullable
              as DateTime,
    ));
  }
}

/// @nodoc
mixin _$ApplicationsPageDto {
  List<ApplicationListItemDto> get items;
  String? get nextCursor;

  /// Create a copy of ApplicationsPageDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $ApplicationsPageDtoCopyWith<ApplicationsPageDto> get copyWith =>
      _$ApplicationsPageDtoCopyWithImpl<ApplicationsPageDto>(
          this as ApplicationsPageDto, _$identity);

  /// Serializes this ApplicationsPageDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is ApplicationsPageDto &&
            const DeepCollectionEquality().equals(other.items, items) &&
            (identical(other.nextCursor, nextCursor) ||
                other.nextCursor == nextCursor));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(
      runtimeType, const DeepCollectionEquality().hash(items), nextCursor);

  @override
  String toString() {
    return 'ApplicationsPageDto(items: $items, nextCursor: $nextCursor)';
  }
}

/// @nodoc
abstract mixin class $ApplicationsPageDtoCopyWith<$Res> {
  factory $ApplicationsPageDtoCopyWith(
          ApplicationsPageDto value, $Res Function(ApplicationsPageDto) _then) =
      _$ApplicationsPageDtoCopyWithImpl;
  @useResult
  $Res call({List<ApplicationListItemDto> items, String? nextCursor});
}

/// @nodoc
class _$ApplicationsPageDtoCopyWithImpl<$Res>
    implements $ApplicationsPageDtoCopyWith<$Res> {
  _$ApplicationsPageDtoCopyWithImpl(this._self, this._then);

  final ApplicationsPageDto _self;
  final $Res Function(ApplicationsPageDto) _then;

  /// Create a copy of ApplicationsPageDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? items = null,
    Object? nextCursor = freezed,
  }) {
    return _then(_self.copyWith(
      items: null == items
          ? _self.items
          : items // ignore: cast_nullable_to_non_nullable
              as List<ApplicationListItemDto>,
      nextCursor: freezed == nextCursor
          ? _self.nextCursor
          : nextCursor // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// Adds pattern-matching-related methods to [ApplicationsPageDto].
extension ApplicationsPageDtoPatterns on ApplicationsPageDto {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_ApplicationsPageDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _ApplicationsPageDto() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_ApplicationsPageDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicationsPageDto():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_ApplicationsPageDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicationsPageDto() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(List<ApplicationListItemDto> items, String? nextCursor)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _ApplicationsPageDto() when $default != null:
        return $default(_that.items, _that.nextCursor);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(List<ApplicationListItemDto> items, String? nextCursor)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicationsPageDto():
        return $default(_that.items, _that.nextCursor);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(List<ApplicationListItemDto> items, String? nextCursor)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicationsPageDto() when $default != null:
        return $default(_that.items, _that.nextCursor);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _ApplicationsPageDto implements ApplicationsPageDto {
  const _ApplicationsPageDto(
      {required final List<ApplicationListItemDto> items, this.nextCursor})
      : _items = items;
  factory _ApplicationsPageDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicationsPageDtoFromJson(json);

  final List<ApplicationListItemDto> _items;
  @override
  List<ApplicationListItemDto> get items {
    if (_items is EqualUnmodifiableListView) return _items;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_items);
  }

  @override
  final String? nextCursor;

  /// Create a copy of ApplicationsPageDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$ApplicationsPageDtoCopyWith<_ApplicationsPageDto> get copyWith =>
      __$ApplicationsPageDtoCopyWithImpl<_ApplicationsPageDto>(
          this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$ApplicationsPageDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _ApplicationsPageDto &&
            const DeepCollectionEquality().equals(other._items, _items) &&
            (identical(other.nextCursor, nextCursor) ||
                other.nextCursor == nextCursor));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(
      runtimeType, const DeepCollectionEquality().hash(_items), nextCursor);

  @override
  String toString() {
    return 'ApplicationsPageDto(items: $items, nextCursor: $nextCursor)';
  }
}

/// @nodoc
abstract mixin class _$ApplicationsPageDtoCopyWith<$Res>
    implements $ApplicationsPageDtoCopyWith<$Res> {
  factory _$ApplicationsPageDtoCopyWith(_ApplicationsPageDto value,
          $Res Function(_ApplicationsPageDto) _then) =
      __$ApplicationsPageDtoCopyWithImpl;
  @override
  @useResult
  $Res call({List<ApplicationListItemDto> items, String? nextCursor});
}

/// @nodoc
class __$ApplicationsPageDtoCopyWithImpl<$Res>
    implements _$ApplicationsPageDtoCopyWith<$Res> {
  __$ApplicationsPageDtoCopyWithImpl(this._self, this._then);

  final _ApplicationsPageDto _self;
  final $Res Function(_ApplicationsPageDto) _then;

  /// Create a copy of ApplicationsPageDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? items = null,
    Object? nextCursor = freezed,
  }) {
    return _then(_ApplicationsPageDto(
      items: null == items
          ? _self._items
          : items // ignore: cast_nullable_to_non_nullable
              as List<ApplicationListItemDto>,
      nextCursor: freezed == nextCursor
          ? _self.nextCursor
          : nextCursor // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// @nodoc
mixin _$ApplicationListItemDto {
  ApplicationDto get application;
  JobSummaryDto get job;
  EmployerSummaryDto get employer;

  /// Create a copy of ApplicationListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $ApplicationListItemDtoCopyWith<ApplicationListItemDto> get copyWith =>
      _$ApplicationListItemDtoCopyWithImpl<ApplicationListItemDto>(
          this as ApplicationListItemDto, _$identity);

  /// Serializes this ApplicationListItemDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is ApplicationListItemDto &&
            (identical(other.application, application) ||
                other.application == application) &&
            (identical(other.job, job) || other.job == job) &&
            (identical(other.employer, employer) ||
                other.employer == employer));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, application, job, employer);

  @override
  String toString() {
    return 'ApplicationListItemDto(application: $application, job: $job, employer: $employer)';
  }
}

/// @nodoc
abstract mixin class $ApplicationListItemDtoCopyWith<$Res> {
  factory $ApplicationListItemDtoCopyWith(ApplicationListItemDto value,
          $Res Function(ApplicationListItemDto) _then) =
      _$ApplicationListItemDtoCopyWithImpl;
  @useResult
  $Res call(
      {ApplicationDto application,
      JobSummaryDto job,
      EmployerSummaryDto employer});

  $ApplicationDtoCopyWith<$Res> get application;
  $JobSummaryDtoCopyWith<$Res> get job;
  $EmployerSummaryDtoCopyWith<$Res> get employer;
}

/// @nodoc
class _$ApplicationListItemDtoCopyWithImpl<$Res>
    implements $ApplicationListItemDtoCopyWith<$Res> {
  _$ApplicationListItemDtoCopyWithImpl(this._self, this._then);

  final ApplicationListItemDto _self;
  final $Res Function(ApplicationListItemDto) _then;

  /// Create a copy of ApplicationListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? application = null,
    Object? job = null,
    Object? employer = null,
  }) {
    return _then(_self.copyWith(
      application: null == application
          ? _self.application
          : application // ignore: cast_nullable_to_non_nullable
              as ApplicationDto,
      job: null == job
          ? _self.job
          : job // ignore: cast_nullable_to_non_nullable
              as JobSummaryDto,
      employer: null == employer
          ? _self.employer
          : employer // ignore: cast_nullable_to_non_nullable
              as EmployerSummaryDto,
    ));
  }

  /// Create a copy of ApplicationListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $ApplicationDtoCopyWith<$Res> get application {
    return $ApplicationDtoCopyWith<$Res>(_self.application, (value) {
      return _then(_self.copyWith(application: value));
    });
  }

  /// Create a copy of ApplicationListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $JobSummaryDtoCopyWith<$Res> get job {
    return $JobSummaryDtoCopyWith<$Res>(_self.job, (value) {
      return _then(_self.copyWith(job: value));
    });
  }

  /// Create a copy of ApplicationListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $EmployerSummaryDtoCopyWith<$Res> get employer {
    return $EmployerSummaryDtoCopyWith<$Res>(_self.employer, (value) {
      return _then(_self.copyWith(employer: value));
    });
  }
}

/// Adds pattern-matching-related methods to [ApplicationListItemDto].
extension ApplicationListItemDtoPatterns on ApplicationListItemDto {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_ApplicationListItemDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _ApplicationListItemDto() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_ApplicationListItemDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicationListItemDto():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_ApplicationListItemDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicationListItemDto() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(ApplicationDto application, JobSummaryDto job,
            EmployerSummaryDto employer)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _ApplicationListItemDto() when $default != null:
        return $default(_that.application, _that.job, _that.employer);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(ApplicationDto application, JobSummaryDto job,
            EmployerSummaryDto employer)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicationListItemDto():
        return $default(_that.application, _that.job, _that.employer);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(ApplicationDto application, JobSummaryDto job,
            EmployerSummaryDto employer)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ApplicationListItemDto() when $default != null:
        return $default(_that.application, _that.job, _that.employer);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _ApplicationListItemDto implements ApplicationListItemDto {
  const _ApplicationListItemDto(
      {required this.application, required this.job, required this.employer});
  factory _ApplicationListItemDto.fromJson(Map<String, dynamic> json) =>
      _$ApplicationListItemDtoFromJson(json);

  @override
  final ApplicationDto application;
  @override
  final JobSummaryDto job;
  @override
  final EmployerSummaryDto employer;

  /// Create a copy of ApplicationListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$ApplicationListItemDtoCopyWith<_ApplicationListItemDto> get copyWith =>
      __$ApplicationListItemDtoCopyWithImpl<_ApplicationListItemDto>(
          this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$ApplicationListItemDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _ApplicationListItemDto &&
            (identical(other.application, application) ||
                other.application == application) &&
            (identical(other.job, job) || other.job == job) &&
            (identical(other.employer, employer) ||
                other.employer == employer));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, application, job, employer);

  @override
  String toString() {
    return 'ApplicationListItemDto(application: $application, job: $job, employer: $employer)';
  }
}

/// @nodoc
abstract mixin class _$ApplicationListItemDtoCopyWith<$Res>
    implements $ApplicationListItemDtoCopyWith<$Res> {
  factory _$ApplicationListItemDtoCopyWith(_ApplicationListItemDto value,
          $Res Function(_ApplicationListItemDto) _then) =
      __$ApplicationListItemDtoCopyWithImpl;
  @override
  @useResult
  $Res call(
      {ApplicationDto application,
      JobSummaryDto job,
      EmployerSummaryDto employer});

  @override
  $ApplicationDtoCopyWith<$Res> get application;
  @override
  $JobSummaryDtoCopyWith<$Res> get job;
  @override
  $EmployerSummaryDtoCopyWith<$Res> get employer;
}

/// @nodoc
class __$ApplicationListItemDtoCopyWithImpl<$Res>
    implements _$ApplicationListItemDtoCopyWith<$Res> {
  __$ApplicationListItemDtoCopyWithImpl(this._self, this._then);

  final _ApplicationListItemDto _self;
  final $Res Function(_ApplicationListItemDto) _then;

  /// Create a copy of ApplicationListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? application = null,
    Object? job = null,
    Object? employer = null,
  }) {
    return _then(_ApplicationListItemDto(
      application: null == application
          ? _self.application
          : application // ignore: cast_nullable_to_non_nullable
              as ApplicationDto,
      job: null == job
          ? _self.job
          : job // ignore: cast_nullable_to_non_nullable
              as JobSummaryDto,
      employer: null == employer
          ? _self.employer
          : employer // ignore: cast_nullable_to_non_nullable
              as EmployerSummaryDto,
    ));
  }

  /// Create a copy of ApplicationListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $ApplicationDtoCopyWith<$Res> get application {
    return $ApplicationDtoCopyWith<$Res>(_self.application, (value) {
      return _then(_self.copyWith(application: value));
    });
  }

  /// Create a copy of ApplicationListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $JobSummaryDtoCopyWith<$Res> get job {
    return $JobSummaryDtoCopyWith<$Res>(_self.job, (value) {
      return _then(_self.copyWith(job: value));
    });
  }

  /// Create a copy of ApplicationListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $EmployerSummaryDtoCopyWith<$Res> get employer {
    return $EmployerSummaryDtoCopyWith<$Res>(_self.employer, (value) {
      return _then(_self.copyWith(employer: value));
    });
  }
}

/// @nodoc
mixin _$SavedJobsPageDto {
  List<SavedJobListItemDto> get items;
  String? get nextCursor;

  /// Create a copy of SavedJobsPageDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $SavedJobsPageDtoCopyWith<SavedJobsPageDto> get copyWith =>
      _$SavedJobsPageDtoCopyWithImpl<SavedJobsPageDto>(
          this as SavedJobsPageDto, _$identity);

  /// Serializes this SavedJobsPageDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is SavedJobsPageDto &&
            const DeepCollectionEquality().equals(other.items, items) &&
            (identical(other.nextCursor, nextCursor) ||
                other.nextCursor == nextCursor));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(
      runtimeType, const DeepCollectionEquality().hash(items), nextCursor);

  @override
  String toString() {
    return 'SavedJobsPageDto(items: $items, nextCursor: $nextCursor)';
  }
}

/// @nodoc
abstract mixin class $SavedJobsPageDtoCopyWith<$Res> {
  factory $SavedJobsPageDtoCopyWith(
          SavedJobsPageDto value, $Res Function(SavedJobsPageDto) _then) =
      _$SavedJobsPageDtoCopyWithImpl;
  @useResult
  $Res call({List<SavedJobListItemDto> items, String? nextCursor});
}

/// @nodoc
class _$SavedJobsPageDtoCopyWithImpl<$Res>
    implements $SavedJobsPageDtoCopyWith<$Res> {
  _$SavedJobsPageDtoCopyWithImpl(this._self, this._then);

  final SavedJobsPageDto _self;
  final $Res Function(SavedJobsPageDto) _then;

  /// Create a copy of SavedJobsPageDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? items = null,
    Object? nextCursor = freezed,
  }) {
    return _then(_self.copyWith(
      items: null == items
          ? _self.items
          : items // ignore: cast_nullable_to_non_nullable
              as List<SavedJobListItemDto>,
      nextCursor: freezed == nextCursor
          ? _self.nextCursor
          : nextCursor // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// Adds pattern-matching-related methods to [SavedJobsPageDto].
extension SavedJobsPageDtoPatterns on SavedJobsPageDto {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_SavedJobsPageDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _SavedJobsPageDto() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_SavedJobsPageDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedJobsPageDto():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_SavedJobsPageDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedJobsPageDto() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(List<SavedJobListItemDto> items, String? nextCursor)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _SavedJobsPageDto() when $default != null:
        return $default(_that.items, _that.nextCursor);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(List<SavedJobListItemDto> items, String? nextCursor)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedJobsPageDto():
        return $default(_that.items, _that.nextCursor);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(List<SavedJobListItemDto> items, String? nextCursor)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedJobsPageDto() when $default != null:
        return $default(_that.items, _that.nextCursor);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _SavedJobsPageDto implements SavedJobsPageDto {
  const _SavedJobsPageDto(
      {required final List<SavedJobListItemDto> items, this.nextCursor})
      : _items = items;
  factory _SavedJobsPageDto.fromJson(Map<String, dynamic> json) =>
      _$SavedJobsPageDtoFromJson(json);

  final List<SavedJobListItemDto> _items;
  @override
  List<SavedJobListItemDto> get items {
    if (_items is EqualUnmodifiableListView) return _items;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_items);
  }

  @override
  final String? nextCursor;

  /// Create a copy of SavedJobsPageDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$SavedJobsPageDtoCopyWith<_SavedJobsPageDto> get copyWith =>
      __$SavedJobsPageDtoCopyWithImpl<_SavedJobsPageDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$SavedJobsPageDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _SavedJobsPageDto &&
            const DeepCollectionEquality().equals(other._items, _items) &&
            (identical(other.nextCursor, nextCursor) ||
                other.nextCursor == nextCursor));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(
      runtimeType, const DeepCollectionEquality().hash(_items), nextCursor);

  @override
  String toString() {
    return 'SavedJobsPageDto(items: $items, nextCursor: $nextCursor)';
  }
}

/// @nodoc
abstract mixin class _$SavedJobsPageDtoCopyWith<$Res>
    implements $SavedJobsPageDtoCopyWith<$Res> {
  factory _$SavedJobsPageDtoCopyWith(
          _SavedJobsPageDto value, $Res Function(_SavedJobsPageDto) _then) =
      __$SavedJobsPageDtoCopyWithImpl;
  @override
  @useResult
  $Res call({List<SavedJobListItemDto> items, String? nextCursor});
}

/// @nodoc
class __$SavedJobsPageDtoCopyWithImpl<$Res>
    implements _$SavedJobsPageDtoCopyWith<$Res> {
  __$SavedJobsPageDtoCopyWithImpl(this._self, this._then);

  final _SavedJobsPageDto _self;
  final $Res Function(_SavedJobsPageDto) _then;

  /// Create a copy of SavedJobsPageDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? items = null,
    Object? nextCursor = freezed,
  }) {
    return _then(_SavedJobsPageDto(
      items: null == items
          ? _self._items
          : items // ignore: cast_nullable_to_non_nullable
              as List<SavedJobListItemDto>,
      nextCursor: freezed == nextCursor
          ? _self.nextCursor
          : nextCursor // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// @nodoc
mixin _$SavedJobListItemDto {
  SavedJobDto get saved;
  JobSummaryDto get job;
  EmployerSummaryDto get employer;
  MatchSummaryDto? get match;

  /// Create a copy of SavedJobListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $SavedJobListItemDtoCopyWith<SavedJobListItemDto> get copyWith =>
      _$SavedJobListItemDtoCopyWithImpl<SavedJobListItemDto>(
          this as SavedJobListItemDto, _$identity);

  /// Serializes this SavedJobListItemDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is SavedJobListItemDto &&
            (identical(other.saved, saved) || other.saved == saved) &&
            (identical(other.job, job) || other.job == job) &&
            (identical(other.employer, employer) ||
                other.employer == employer) &&
            (identical(other.match, match) || other.match == match));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, saved, job, employer, match);

  @override
  String toString() {
    return 'SavedJobListItemDto(saved: $saved, job: $job, employer: $employer, match: $match)';
  }
}

/// @nodoc
abstract mixin class $SavedJobListItemDtoCopyWith<$Res> {
  factory $SavedJobListItemDtoCopyWith(
          SavedJobListItemDto value, $Res Function(SavedJobListItemDto) _then) =
      _$SavedJobListItemDtoCopyWithImpl;
  @useResult
  $Res call(
      {SavedJobDto saved,
      JobSummaryDto job,
      EmployerSummaryDto employer,
      MatchSummaryDto? match});

  $SavedJobDtoCopyWith<$Res> get saved;
  $JobSummaryDtoCopyWith<$Res> get job;
  $EmployerSummaryDtoCopyWith<$Res> get employer;
  $MatchSummaryDtoCopyWith<$Res>? get match;
}

/// @nodoc
class _$SavedJobListItemDtoCopyWithImpl<$Res>
    implements $SavedJobListItemDtoCopyWith<$Res> {
  _$SavedJobListItemDtoCopyWithImpl(this._self, this._then);

  final SavedJobListItemDto _self;
  final $Res Function(SavedJobListItemDto) _then;

  /// Create a copy of SavedJobListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? saved = null,
    Object? job = null,
    Object? employer = null,
    Object? match = freezed,
  }) {
    return _then(_self.copyWith(
      saved: null == saved
          ? _self.saved
          : saved // ignore: cast_nullable_to_non_nullable
              as SavedJobDto,
      job: null == job
          ? _self.job
          : job // ignore: cast_nullable_to_non_nullable
              as JobSummaryDto,
      employer: null == employer
          ? _self.employer
          : employer // ignore: cast_nullable_to_non_nullable
              as EmployerSummaryDto,
      match: freezed == match
          ? _self.match
          : match // ignore: cast_nullable_to_non_nullable
              as MatchSummaryDto?,
    ));
  }

  /// Create a copy of SavedJobListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $SavedJobDtoCopyWith<$Res> get saved {
    return $SavedJobDtoCopyWith<$Res>(_self.saved, (value) {
      return _then(_self.copyWith(saved: value));
    });
  }

  /// Create a copy of SavedJobListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $JobSummaryDtoCopyWith<$Res> get job {
    return $JobSummaryDtoCopyWith<$Res>(_self.job, (value) {
      return _then(_self.copyWith(job: value));
    });
  }

  /// Create a copy of SavedJobListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $EmployerSummaryDtoCopyWith<$Res> get employer {
    return $EmployerSummaryDtoCopyWith<$Res>(_self.employer, (value) {
      return _then(_self.copyWith(employer: value));
    });
  }

  /// Create a copy of SavedJobListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $MatchSummaryDtoCopyWith<$Res>? get match {
    if (_self.match == null) {
      return null;
    }

    return $MatchSummaryDtoCopyWith<$Res>(_self.match!, (value) {
      return _then(_self.copyWith(match: value));
    });
  }
}

/// Adds pattern-matching-related methods to [SavedJobListItemDto].
extension SavedJobListItemDtoPatterns on SavedJobListItemDto {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_SavedJobListItemDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _SavedJobListItemDto() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_SavedJobListItemDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedJobListItemDto():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_SavedJobListItemDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedJobListItemDto() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(SavedJobDto saved, JobSummaryDto job,
            EmployerSummaryDto employer, MatchSummaryDto? match)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _SavedJobListItemDto() when $default != null:
        return $default(_that.saved, _that.job, _that.employer, _that.match);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(SavedJobDto saved, JobSummaryDto job,
            EmployerSummaryDto employer, MatchSummaryDto? match)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedJobListItemDto():
        return $default(_that.saved, _that.job, _that.employer, _that.match);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(SavedJobDto saved, JobSummaryDto job,
            EmployerSummaryDto employer, MatchSummaryDto? match)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedJobListItemDto() when $default != null:
        return $default(_that.saved, _that.job, _that.employer, _that.match);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _SavedJobListItemDto implements SavedJobListItemDto {
  const _SavedJobListItemDto(
      {required this.saved,
      required this.job,
      required this.employer,
      this.match});
  factory _SavedJobListItemDto.fromJson(Map<String, dynamic> json) =>
      _$SavedJobListItemDtoFromJson(json);

  @override
  final SavedJobDto saved;
  @override
  final JobSummaryDto job;
  @override
  final EmployerSummaryDto employer;
  @override
  final MatchSummaryDto? match;

  /// Create a copy of SavedJobListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$SavedJobListItemDtoCopyWith<_SavedJobListItemDto> get copyWith =>
      __$SavedJobListItemDtoCopyWithImpl<_SavedJobListItemDto>(
          this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$SavedJobListItemDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _SavedJobListItemDto &&
            (identical(other.saved, saved) || other.saved == saved) &&
            (identical(other.job, job) || other.job == job) &&
            (identical(other.employer, employer) ||
                other.employer == employer) &&
            (identical(other.match, match) || other.match == match));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, saved, job, employer, match);

  @override
  String toString() {
    return 'SavedJobListItemDto(saved: $saved, job: $job, employer: $employer, match: $match)';
  }
}

/// @nodoc
abstract mixin class _$SavedJobListItemDtoCopyWith<$Res>
    implements $SavedJobListItemDtoCopyWith<$Res> {
  factory _$SavedJobListItemDtoCopyWith(_SavedJobListItemDto value,
          $Res Function(_SavedJobListItemDto) _then) =
      __$SavedJobListItemDtoCopyWithImpl;
  @override
  @useResult
  $Res call(
      {SavedJobDto saved,
      JobSummaryDto job,
      EmployerSummaryDto employer,
      MatchSummaryDto? match});

  @override
  $SavedJobDtoCopyWith<$Res> get saved;
  @override
  $JobSummaryDtoCopyWith<$Res> get job;
  @override
  $EmployerSummaryDtoCopyWith<$Res> get employer;
  @override
  $MatchSummaryDtoCopyWith<$Res>? get match;
}

/// @nodoc
class __$SavedJobListItemDtoCopyWithImpl<$Res>
    implements _$SavedJobListItemDtoCopyWith<$Res> {
  __$SavedJobListItemDtoCopyWithImpl(this._self, this._then);

  final _SavedJobListItemDto _self;
  final $Res Function(_SavedJobListItemDto) _then;

  /// Create a copy of SavedJobListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? saved = null,
    Object? job = null,
    Object? employer = null,
    Object? match = freezed,
  }) {
    return _then(_SavedJobListItemDto(
      saved: null == saved
          ? _self.saved
          : saved // ignore: cast_nullable_to_non_nullable
              as SavedJobDto,
      job: null == job
          ? _self.job
          : job // ignore: cast_nullable_to_non_nullable
              as JobSummaryDto,
      employer: null == employer
          ? _self.employer
          : employer // ignore: cast_nullable_to_non_nullable
              as EmployerSummaryDto,
      match: freezed == match
          ? _self.match
          : match // ignore: cast_nullable_to_non_nullable
              as MatchSummaryDto?,
    ));
  }

  /// Create a copy of SavedJobListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $SavedJobDtoCopyWith<$Res> get saved {
    return $SavedJobDtoCopyWith<$Res>(_self.saved, (value) {
      return _then(_self.copyWith(saved: value));
    });
  }

  /// Create a copy of SavedJobListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $JobSummaryDtoCopyWith<$Res> get job {
    return $JobSummaryDtoCopyWith<$Res>(_self.job, (value) {
      return _then(_self.copyWith(job: value));
    });
  }

  /// Create a copy of SavedJobListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $EmployerSummaryDtoCopyWith<$Res> get employer {
    return $EmployerSummaryDtoCopyWith<$Res>(_self.employer, (value) {
      return _then(_self.copyWith(employer: value));
    });
  }

  /// Create a copy of SavedJobListItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $MatchSummaryDtoCopyWith<$Res>? get match {
    if (_self.match == null) {
      return null;
    }

    return $MatchSummaryDtoCopyWith<$Res>(_self.match!, (value) {
      return _then(_self.copyWith(match: value));
    });
  }
}

// dart format on
