using Jobvago.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace Jobvago.Api.Data;

public class JobvagoDbContext : DbContext
{
    public JobvagoDbContext(DbContextOptions<JobvagoDbContext> options) : base(options)
    {
    }

    public DbSet<Job> Jobs { get; set; }
    public DbSet<Company> Companies { get; set; }
    public DbSet<Location> Locations { get; set; }
    public DbSet<Skill> Skills { get; set; }
    public DbSet<Source> Sources { get; set; }

    public DbSet<JobLocation> JobLocations { get; set; }
    public DbSet<JobSkill> JobSkills { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        modelBuilder.Entity<JobLocation>()
            .HasKey(jl => new { jl.JobID, jl.LocationID });

        modelBuilder.Entity<JobSkill>()
            .HasKey(js => new { js.JobID, js.SkillID });

        // Be explicit about the data type for our decimal properties in the Jobs table.
        // We'll use a precision of 18 (total digits) and a scale of 2 (digits after decimal).
        // This corresponds to SQL Server's DECIMAL(18, 2) type.
        modelBuilder.Entity<Job>(entity =>
        {
            entity.Property(e => e.MinSalary).HasPrecision(18, 2);
            entity.Property(e => e.MaxSalary).HasPrecision(18, 2);
        });
    }
}