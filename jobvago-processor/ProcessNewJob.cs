using System;
using System.Linq;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Collections.Generic;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Jobvago.Api.Data;
using Jobvago.Api.Models;

namespace Jobvago.Processor
{
    public class ProcessNewJob
    {
        private readonly ILogger<ProcessNewJob> _logger;
        private readonly JobvagoDbContext _context;
        private const int UNIQUE_KEY_VIOLATION_ERROR_NUMBER = 2627;

        public ProcessNewJob(ILogger<ProcessNewJob> logger, JobvagoDbContext context)
        {
            _logger = logger;
            _context = context;
        }

        [Function(nameof(ProcessNewJob))]
        public async Task Run(
            [ServiceBusTrigger("new-jobs-queue", Connection = "ServiceBusConnectionString")]
            string myQueueItem
        )
        {
            _logger.LogInformation("C# ServiceBus queue trigger function started processing a message.");

            JobItemDto? rawJob;
            try
            {
                rawJob = JsonSerializer.Deserialize<JobItemDto>(myQueueItem);
                if (rawJob == null || string.IsNullOrWhiteSpace(rawJob.OriginalUrl))
                {
                    _logger.LogError("Failed to deserialize message or message is invalid: {message}", myQueueItem);
                    return;
                }
            }
            catch (JsonException ex)
            {
                _logger.LogError(ex, "JSON Deserialization failed for message: {message}", myQueueItem);
                return;
            }

            _logger.LogInformation("Processing job: '{JobTitle}' from '{Company}'", rawJob.Title, rawJob.CompanyName);
            
            var existingJob = await _context.Jobs
                .AsNoTracking()
                .FirstOrDefaultAsync(j => j.OriginalUrl == rawJob.OriginalUrl);

            if (existingJob != null)
            {
                _logger.LogWarning("Job with URL '{url}' already exists. Updating timestamp.", rawJob.OriginalUrl);
                await UpdateLastSeenTimestampAsync(existingJob.ID);
                return;
            }

            await ProcessJobAsync(rawJob);
        }

        private async Task UpdateLastSeenTimestampAsync(int jobId)
        {
            try
            {
                _context.ChangeTracker.Clear();
                
                var job = await _context.Jobs.FindAsync(jobId);
                if (job != null)
                {
                    job.LastSeenAt = DateTime.UtcNow;
                    await _context.SaveChangesAsync();
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error updating LastSeenAt timestamp for job ID {0}", jobId);
            }
        }

        private async Task ProcessJobAsync(JobItemDto rawJob)
        {
            _context.ChangeTracker.Clear();
            
            var strategy = _context.Database.CreateExecutionStrategy();
            
            await strategy.ExecuteAsync(async () =>
            {
                using var transaction = await _context.Database.BeginTransactionAsync();
                try
                {
                    var existingJob = await _context.Jobs
                        .FirstOrDefaultAsync(j => j.OriginalUrl == rawJob.OriginalUrl);
                    
                    if (existingJob != null)
                    {
                        _logger.LogWarning("Job was created by another process during our processing. Updating timestamp.");
                        existingJob.LastSeenAt = DateTime.UtcNow;
                        await _context.SaveChangesAsync();
                        await transaction.CommitAsync();
                        return;
                    }
                    
                    var company = await GetOrCreateReferenceEntityAsync<Company>(
                        _context.Companies,
                        c => c.Name == rawJob.CompanyName,
                        () => new Company { Name = rawJob.CompanyName }
                    );

                    var source = await GetOrCreateReferenceEntityAsync<Source>(
                        _context.Sources,
                        s => s.Name == rawJob.Source,
                        () => new Source { Name = rawJob.Source }
                    );

                    var (minSalary, maxSalary, currency) = ParseSalaryDetails(rawJob.RawSalaryText, rawJob.Source);

                    var newJob = new Job
                    {
                        JobTitle = rawJob.Title,
                        OriginalUrl = rawJob.OriginalUrl,
                        CompanyID = company.ID,
                        SourceID = source.ID,
                        CreatedAt = DateTime.UtcNow,
                        LastSeenAt = DateTime.UtcNow,
                        MinSalary = minSalary,
                        MaxSalary = maxSalary,
                        Currency = currency,
                        IsRemote = false
                    };

                    _context.Jobs.Add(newJob);
                    await _context.SaveChangesAsync();

                    if (!string.IsNullOrWhiteSpace(rawJob.Location))
                    {
                        var locationNames = rawJob.Location
                            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

                        foreach (var name in locationNames)
                        {
                            if (name.Equals("Remote", StringComparison.OrdinalIgnoreCase))
                            {
                                newJob.IsRemote = true;
                                continue;
                            }

                            var location = await GetOrCreateReferenceEntityAsync<Location>(
                                _context.Locations,
                                l => l.Name == name,
                                () => new Location { Name = name }
                            );

                            _context.JobLocations.Add(new JobLocation
                            {
                                JobID = newJob.ID,
                                LocationID = location.ID
                            });
                        }
                        
                        await _context.SaveChangesAsync();
                    }

                    await transaction.CommitAsync();
                    _logger.LogInformation("Successfully processed and saved new job with ID: {JobId}", newJob.ID);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error in job processing: {0}", ex.Message);
                    await transaction.RollbackAsync();
                    throw;
                }
            });
        }

        private async Task<T> GetOrCreateReferenceEntityAsync<T>(
            DbSet<T> dbSet, 
            System.Linq.Expressions.Expression<Func<T, bool>> predicate,
            Func<T> entityFactory) where T : class
        {
            var entity = await dbSet.FirstOrDefaultAsync(predicate);
            if (entity != null)
            {
                return entity;
            }

            try
            {
                entity = entityFactory();
                dbSet.Add(entity);
                await _context.SaveChangesAsync();
                return entity;
            }
            catch (DbUpdateException ex) when (IsUniqueKeyViolation(ex))
            {
                _logger.LogWarning("Race detected creating {0} - fetching existing entity", typeof(T).Name);
                
                foreach (var entry in _context.ChangeTracker.Entries<T>().ToList())
                {
                    if (entry.State == EntityState.Added)
                    {
                        entry.State = EntityState.Detached;
                    }
                }
                
                return await dbSet.FirstAsync(predicate);
            }
        }

        private bool IsUniqueKeyViolation(DbUpdateException ex)
        {
            return (ex.InnerException as SqlException)?.Number == UNIQUE_KEY_VIOLATION_ERROR_NUMBER;
        }

        private (decimal? MinSalary, decimal? MaxSalary, string? Currency)
        ParseSalaryDetails(string? rawSalaryText, string source)
        {
            if (string.IsNullOrWhiteSpace(rawSalaryText)
                || rawSalaryText.Equals("Unpaid", StringComparison.OrdinalIgnoreCase)
                || !Regex.IsMatch(rawSalaryText, @"\d"))
                return (null, null, null);

            var numbers = Regex.Matches(rawSalaryText, @"\d[\d,.]*")
                .Select(m => decimal.Parse(m.Value.Replace(",", "")))
                .ToList();

            if (!numbers.Any()) return (null, null, null);

            var min = numbers.Min();
            var max = numbers.Max();
            string? curr = null;
            if (rawSalaryText.Contains('₹')) curr = "INR";
            else if (rawSalaryText.Contains('$')) curr = "USD";
            else if (rawSalaryText.Contains('€')) curr = "EUR";
            else if (source.Equals("Internshala", StringComparison.OrdinalIgnoreCase))
                curr = "INR";

            return (min, max, curr);
        }
    }
}
