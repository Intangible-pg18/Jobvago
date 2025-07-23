namespace Jobvago.Api.Models;

public class JobLocation
{
    public int JobID { get; set; }
    public Job Job { get; set; } = null!;

    public int LocationID { get; set; }
    public Location Location { get; set; } = null!;
}