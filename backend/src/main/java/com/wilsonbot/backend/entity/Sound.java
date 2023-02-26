package com.wilsonbot.backend.entity;

import lombok.*;
import lombok.experimental.Accessors;
import javax.persistence.*;
import java.io.Serializable;

@Data
@NoArgsConstructor
@Accessors(chain = true)
@Entity
@Table(name = "sounds")
public class Sound implements Serializable{

    private String sound_id;
    private String sound_name;
    private String category_id;
    private String author_id;
    private Long plays;
    private String date; 
}