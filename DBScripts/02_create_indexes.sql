USE [JobvagoDB];
GO

CREATE NONCLUSTERED INDEX IX_Jobs_CompanyID
ON Jobs(CompanyID);
GO

CREATE NONCLUSTERED INDEX IX_Jobs_SourceID
ON Jobs(SourceID);
GO

CREATE NONCLUSTERED INDEX IX_JobLocations_LocationID
ON JobLocations(LocationID);
GO

CREATE NONCLUSTERED INDEX IX_JobSkills_SkillID
ON JobSkills(SkillID);
GO

PRINT 'Successfully created non-clustered indexes for performance.';