namespace Jobvago.Api.Models;

public class JobSkill
{
    public int JobID { get; set; }
    public Job Job { get; set; } = null!;

    public int SkillID { get; set; }
    public Skill Skill { get; set; } = null!;
}