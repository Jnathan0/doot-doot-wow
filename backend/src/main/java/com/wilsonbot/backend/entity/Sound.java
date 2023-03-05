package com.wilsonbot.backend.entity;

import lombok.*;
import lombok.experimental.Accessors;
import jakarta.persistence.*;

@Data
@NoArgsConstructor
@Entity
@Table(name = "sounds")
public class Sound {
	@Id
    @Column(name = "sound_id")
    private String soundId;
    @Column(name = "sound_name")
    private String soundName;
    @Column(name = "category_id")
    private String categoryId;
    @Column(name = "author_id")
    private String authorId;
    @Column(name = "plays")
    private Long plays;
    @Column(name = "date")
    private String date; 
}