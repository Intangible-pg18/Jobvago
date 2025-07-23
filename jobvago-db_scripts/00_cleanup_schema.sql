IF OBJECT_ID('JobLocations', 'U') IS NOT NULL
    DROP TABLE JobLocations;
GO

IF OBJECT_ID('JobSkills', 'U') IS NOT NULL
    DROP TABLE JobSkills;
GO

IF OBJECT_ID('Jobs', 'U') IS NOT NULL
    DROP TABLE Jobs;
GO

IF OBJECT_ID('Companies', 'U') IS NOT NULL
    DROP TABLE Companies;
GO

IF OBJECT_ID('Locations', 'U') IS NOT NULL
    DROP TABLE Locations;
GO

IF OBJECT_ID('Skills', 'U') IS NOT NULL
    DROP TABLE Skills;
GO

IF OBJECT_ID('Sources', 'U') IS NOT NULL
    DROP TABLE Sources;
GO

PRINT 'Cleanup complete. All Jobvago tables have been dropped.';